from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class LineInput:
    """The minimum a price calculation needs from a cart line."""

    variant_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class PriceBreakdown:
    """Every amount a client is allowed to see, already rounded."""

    currency: str
    subtotal: Decimal
    shipping_fee: Decimal
    tax: Decimal
    total: Decimal
