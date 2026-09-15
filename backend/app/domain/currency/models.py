"""Currency reference data and stored exchange rates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Rate, TimestampMixin


class Currency(Base):
    __tablename__ = "currency"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rate"

    base_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code", ondelete="CASCADE"), primary_key=True
    )
    quote_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code", ondelete="CASCADE"), primary_key=True
    )
    rate: Mapped[Decimal] = mapped_column(Rate, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
