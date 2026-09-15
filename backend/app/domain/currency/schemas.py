from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CurrencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    symbol: str
    decimal_places: int
    is_active: bool


class ExchangeRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base_code: str
    quote_code: str
    rate: Decimal
    source: str
    fetched_at: datetime


class ExchangeRateOverride(BaseModel):
    base_code: str
    quote_code: str
    rate: Decimal
    source: str = "manual"
