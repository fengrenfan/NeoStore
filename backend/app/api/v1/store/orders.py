from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import OrderDep
from app.domain.order.schemas import OrderRead

router = APIRouter(prefix="/orders", tags=["store: orders"])


@router.get("/{number}", response_model=OrderRead)
async def get_order(number: str, orders: OrderDep) -> OrderRead:
    order = await orders.get(number)
    return OrderRead.model_validate(order)
