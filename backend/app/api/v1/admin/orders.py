from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import OrderDep, SessionDep
from app.core.domain_errors import NotFoundError
from app.core.security import AdminDep
from app.domain.order.models import Order
from app.domain.order.schemas import OrderListPage, OrderRead, OrderStatusUpdate
from app.domain.order.state_machine import OrderStatus, allowed_targets

router = APIRouter(prefix="/orders", tags=["admin: orders"])


def _validate_status(raw: str) -> OrderStatus:
    try:
        return OrderStatus(raw.lower())
    except ValueError as exc:
        raise NotFoundError(
            message=f"unknown order status '{raw}'",
            code="INVALID_ORDER_STATUS",
            status_code=422,
        ) from exc


@router.get("", response_model=OrderListPage)
async def list_orders(
    orders: OrderDep,
    _: AdminDep,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrderListPage:
    target = _validate_status(status) if status else None
    rows, total = await orders.list_orders(status=target, limit=limit, offset=offset)
    return OrderListPage(
        items=[OrderRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{ref}", response_model=OrderRead)
async def get_order(ref: str, orders: OrderDep, _: AdminDep) -> OrderRead:
    return OrderRead.model_validate(await orders.get_by_ref(ref))


@router.get("/{ref}/transitions", response_model=list[str])
async def get_transitions(ref: str, orders: OrderDep, _: AdminDep) -> list[str]:
    order: Order = await orders.get_by_ref(ref)
    return allowed_targets(order.status)


@router.patch("/{ref}/status", response_model=OrderRead)
async def update_status(
    ref: str,
    payload: OrderStatusUpdate,
    session: SessionDep,
    orders: OrderDep,
    _: AdminDep,
) -> OrderRead:
    order = await orders.transition(ref, _validate_status(payload.status), payload.note)
    await session.commit()
    return OrderRead.model_validate(order)
