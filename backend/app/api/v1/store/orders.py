from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.deps import OrderDep, SessionDep
from app.core.domain_errors import NotFoundError
from app.domain.order.schemas import OrderRead

router = APIRouter(prefix="/orders", tags=["store: orders"])


@router.get("/{number}", response_model=OrderRead)
async def get_order(number: str, orders: OrderDep) -> OrderRead:
    order = await orders.get(number)
    return OrderRead.model_validate(order)


@router.post("/{number}/pay", response_model=OrderRead)
async def pay_order(number: str, session: SessionDep, orders: OrderDep) -> OrderRead:
    """Stand-in for the payment gateway's callback.

    A real integration never exposes this: the provider POSTs to a webhook
    whose signature we verify, or the shopper returns from a hosted checkout
    page carrying a token. Until that exists, this route is what lets the demo
    close the loop — intent created at checkout, confirmation accepted here,
    reserved stock committed, order moved to ``paid``.

    It is therefore destructive by nature and gated behind
    ``ENABLE_MOCK_PAYMENTS``. The route 404s when that is off so a production
    deployment does not even advertise its existence.
    """
    if not settings.enable_mock_payments:
        raise NotFoundError(
            message="order payment confirmation is not available",
            code="MOCK_PAYMENTS_DISABLED",
        )

    order = await orders.pay(number)
    await session.commit()
    return OrderRead.model_validate(order)
