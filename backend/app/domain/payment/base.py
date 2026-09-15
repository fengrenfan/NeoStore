"""Payment provider contract.

Shaped like a real gateway (intent → confirm → refund) so swapping the mock for
Stripe/PayPal/Adyen is a new class, not a refactor of the callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid a runtime import cycle with the order aggregate
    from app.domain.order.models import Order


@dataclass(frozen=True, slots=True)
class PaymentIntent:
    provider: str
    provider_ref: str
    amount: Decimal
    currency: str
    #: e.g. ``requires_confirmation`` / ``requires_action`` / ``succeeded``
    status: str


@dataclass(frozen=True, slots=True)
class PaymentResult:
    success: bool
    provider_ref: str
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    code: str = "base"

    @abstractmethod
    async def create_intent(self, order: Order) -> PaymentIntent:
        """Register the amount with the gateway and return a reference."""

    @abstractmethod
    async def confirm(self, provider_ref: str) -> PaymentResult:
        """Finalise an intent (what a webhook or redirect callback triggers)."""

    @abstractmethod
    async def refund(self, provider_ref: str, amount: Decimal) -> PaymentResult:
        """Refund all or part of a captured payment."""
