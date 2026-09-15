"""Stock levels and the movement ledger behind them."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class InventoryItem(Base):
    """One row per variant. ``reserved`` is stock held by unpaid orders."""

    __tablename__ = "inventory_item"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variant.id", ondelete="CASCADE"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @property
    def available(self) -> int:
        return self.quantity - self.reserved


class StockMovement(Base, TimestampMixin):
    """Append-only audit trail: every change to stock is explainable."""

    __tablename__ = "stock_movement"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
