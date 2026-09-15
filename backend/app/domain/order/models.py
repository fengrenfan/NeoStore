"""Order aggregate.

Two rules are non-negotiable here:

1. ``OrderLine`` **snapshots** product name, label, SKU and unit price. Orders
   are historical records; renaming or repricing a product must never rewrite
   what a customer bought.
2. Status changes go through ``mark_*`` helpers, each appending an
   ``OrderEvent`` so the lifecycle is auditable.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonB, Money, TimestampMixin, str_enum
from app.domain.order.state_machine import OrderStatus, assert_transition


class Order(Base, TimestampMixin):
    #: ``order`` is a reserved word in PostgreSQL and SQLite, hence the plural.
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status"),
        nullable=False,
        default=OrderStatus.DRAFT,
        index=True,
    )
    region_code: Mapped[str] = mapped_column(String(16), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    shipping_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )

    lines: Mapped[list[OrderLine]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[list[OrderEvent]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderEvent.created_at",
    )

    def _transition(self, target: OrderStatus, note: str | None = None) -> None:
        assert_transition(self.status, target)
        previous = self.status
        self.status = target
        self.events.append(
            OrderEvent(from_status=previous, to_status=target, note=note)
        )

    def mark_awaiting_payment(self, note: str | None = None) -> None:
        self._transition(OrderStatus.AWAITING_PAYMENT, note)

    def mark_paid(self, note: str | None = None) -> None:
        self._transition(OrderStatus.PAID, note)

    def mark_fulfilled(self, note: str | None = None) -> None:
        self._transition(OrderStatus.FULFILLED, note)

    def mark_completed(self, note: str | None = None) -> None:
        self._transition(OrderStatus.COMPLETED, note)

    def cancel(self, note: str | None = None) -> None:
        self._transition(OrderStatus.CANCELLED, note)

    def refund(self, note: str | None = None) -> None:
        self._transition(OrderStatus.REFUNDED, note)


class OrderLine(Base):
    """A frozen record of what was bought. No FK to the catalog, on purpose."""

    __tablename__ = "order_line"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Kept for analytics only; deliberately not a foreign key.
    variant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)

    order: Mapped[Order] = relationship(back_populates="lines")


class OrderEvent(Base):
    __tablename__ = "order_event"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[OrderStatus | None] = mapped_column(
        str_enum(OrderStatus, "order_status"), nullable=True
    )
    to_status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="events")
