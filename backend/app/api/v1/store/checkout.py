from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from app.core.deps import LocaleDep, OrderDep, SessionDep
from app.domain.order.schemas import CheckoutRequest, OrderRead

router = APIRouter(tags=["store: checkout"])


@router.post("/checkout", response_model=OrderRead, status_code=201)
async def checkout(
    payload: CheckoutRequest,
    session: SessionDep,
    orders: OrderDep,
    locale: LocaleDep,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", description="Replay-safe checkout"),
    ] = None,
) -> OrderRead:
    order = await orders.checkout(
        cart_token=payload.cart_token,
        email=payload.email,
        shipping_address=payload.shipping_address,
        idempotency_key=idempotency_key,
        locale=locale,
        provider_code=payload.payment_provider,
    )
    await session.commit()
    return OrderRead.model_validate(order)
