"""Mock provider used until a real gateway is wired up.

It behaves like a real card gateway in one respect that matters: an intent is
created first and only succeeds once confirmed, so the order lifecycle exercises
the same two-step path production will use.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.core.domain_errors import DomainError
from app.domain.payment.base import PaymentIntent, PaymentProvider, PaymentResult

if TYPE_CHECKING:
    from app.domain.order.models import Order


class MockPaymentProvider(PaymentProvider):
    code = "mock"

    def __init__(self) -> None:
        self._intents: dict[str, dict[str, Any]] = {}

    async def create_intent(self, order: Order) -> PaymentIntent:
        provider_ref = f"mock_{uuid.uuid4().hex}"
        self._intents[provider_ref] = {
            "order_number": order.number,
            "amount": str(order.total),
            "currency": order.currency_code,
            "captured": False,
        }
        return PaymentIntent(
            provider=self.code,
            provider_ref=provider_ref,
            amount=order.total,
            currency=order.currency_code,
            status="requires_confirmation",
        )

    async def confirm(self, provider_ref: str) -> PaymentResult:
        intent = self._intents.get(provider_ref)
        if intent is None:
            return PaymentResult(
                success=False,
                provider_ref=provider_ref,
                raw={"reason": "unknown_intent"},
            )
        intent["captured"] = True
        return PaymentResult(success=True, provider_ref=provider_ref, raw={"provider": self.code})

    async def refund(self, provider_ref: str, amount: Decimal) -> PaymentResult:
        intent = self._intents.get(provider_ref)
        if intent is None or not intent.get("captured"):
            return PaymentResult(
                success=False,
                provider_ref=provider_ref,
                raw={"reason": "not_captured"},
            )
        return PaymentResult(
            success=True,
            provider_ref=provider_ref,
            raw={"provider": self.code, "refunded": str(amount)},
        )


_REGISTRY: dict[str, PaymentProvider] = {}


def register_provider(provider: PaymentProvider) -> PaymentProvider:
    _REGISTRY[provider.code] = provider
    return provider


def get_payment_provider(code: str) -> PaymentProvider:
    provider = _REGISTRY.get(code)
    if provider is None:
        raise DomainError(
            message=f"payment provider '{code}' is not available",
            code="UNKNOWN_PAYMENT_PROVIDER",
            details={"provider": code, "available": sorted(_REGISTRY)},
        )
    return provider


register_provider(MockPaymentProvider())
