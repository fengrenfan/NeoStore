from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    variant_id: uuid.UUID | None
    product_name: str
    variant_label: str | None
    sku: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    currency_code: str


class OrderEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    status: str
    region_code: str
    currency_code: str
    email: str
    shipping_address: dict
    subtotal: Decimal
    shipping_fee: Decimal
    tax: Decimal
    total: Decimal
    lines: list[OrderLineRead] = []
    events: list[OrderEventRead] = []


class CheckoutRequest(BaseModel):
    cart_token: str
    email: str
    shipping_address: dict
    payment_provider: str = "mock"


class OrderStatusUpdate(BaseModel):
    status: str
    note: str | None = None


class InventoryAdjustment(BaseModel):
    delta: int
    reason: str = "manual"
    note: str | None = None


class OrderListPage(BaseModel):
    items: list[OrderRead]
    total: int
    limit: int
    offset: int
