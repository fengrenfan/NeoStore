"""Anonymous carts. Identity is an unguessable token, not a logged-in user."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Money, TimestampMixin, str_enum


class CartStatus(enum.StrEnum):
    ACTIVE = "active"
    CONVERTED = "converted"
    ABANDONED = "abandoned"


class Cart(Base, TimestampMixin):
    __tablename__ = "cart"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    region_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("region.code"), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), nullable=False
    )
    status: Mapped[CartStatus] = mapped_column(
        str_enum(CartStatus, "cart_status"), nullable=False, default=CartStatus.ACTIVE
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lines: Mapped[list[CartLine]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CartLine.position",
    )


class CartLine(Base):
    __tablename__ = "cart_line"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cart.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variant.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Snapshot taken when the line was added, so mid-session price changes
    #: never make the cart total jump under the customer.
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    cart: Mapped[Cart] = relationship(back_populates="lines")
