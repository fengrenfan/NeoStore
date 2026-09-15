"""Domain error hierarchy — framework-free.

Kept separate from :mod:`app.core.errors` so that ``app.domain`` and
``app.integrations`` can raise and catch these without importing FastAPI, which
the layering rule forbids.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for expected, client-facing failures."""

    code = "DOMAIN_ERROR"
    status_code = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status_code = 404


class ValidationFailedError(DomainError):
    code = "VALIDATION_FAILED"
    status_code = 422


class InsufficientStockError(DomainError):
    code = "INSUFFICIENT_STOCK"
    status_code = 409


class CartExpiredError(DomainError):
    code = "CART_EXPIRED"
    status_code = 410


class PaymentFailedError(DomainError):
    code = "PAYMENT_FAILED"
    status_code = 402


class IdempotencyConflictError(DomainError):
    code = "IDEMPOTENCY_CONFLICT"
    status_code = 409


class ExchangeRateUnavailableError(DomainError):
    code = "EXCHANGE_RATE_UNAVAILABLE"
    status_code = 503


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"
    status_code = 401


class InvalidStatusTransitionError(DomainError):
    code = "INVALID_STATUS_TRANSITION"
    status_code = 409
