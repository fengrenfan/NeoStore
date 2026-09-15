"""Order status machine.

``OrderStatus`` lives here rather than in ``models`` so that ``models`` can
import it — the reverse would be a circular import.
"""

from __future__ import annotations

import enum

from app.core.domain_errors import InvalidStatusTransitionError


class OrderStatus(enum.StrEnum):
    DRAFT = "draft"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    FULFILLED = "fulfilled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.AWAITING_PAYMENT, OrderStatus.CANCELLED}),
    OrderStatus.AWAITING_PAYMENT: frozenset({OrderStatus.PAID, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.FULFILLED, OrderStatus.REFUNDED}),
    OrderStatus.FULFILLED: frozenset({OrderStatus.COMPLETED, OrderStatus.REFUNDED}),
    OrderStatus.COMPLETED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}


def assert_transition(current: OrderStatus, target: OrderStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidStatusTransitionError(
            message=f"cannot move an order from '{current}' to '{target}'",
            details={"from": str(current), "to": str(target)},
        )


def allowed_targets(current: OrderStatus) -> list[str]:
    return sorted(str(status) for status in ALLOWED_TRANSITIONS.get(current, frozenset()))
