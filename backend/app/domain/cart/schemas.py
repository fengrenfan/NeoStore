from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CartLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    currency_code: str


class CartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: str
    region_code: str
    currency_code: str
    status: str
    lines: list[CartLineRead] = []


class CartCreate(BaseModel):
    region: str | None = None


class CartLineWrite(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)


class CartLineUpdate(BaseModel):
    quantity: int = Field(ge=0)


class CartTotalsRead(BaseModel):
    currency: str
    subtotal: Decimal
    shipping_fee: Decimal
    tax: Decimal
    total: Decimal
