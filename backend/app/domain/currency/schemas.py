from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.serialization import UtcDatetime


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
    fetched_at: UtcDatetime


class ExchangeRateOverride(BaseModel):
    base_code: str
    quote_code: str
    rate: Decimal
    source: str = "manual"
