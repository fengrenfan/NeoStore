"""Renders domain errors as the unified HTTP error envelope.

The exception types themselves live in :mod:`app.core.domain_errors` so the
domain layer can use them without depending on FastAPI. They are re-exported
here for convenience.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.domain_errors import (  # noqa: F401  (re-exported)
    CartExpiredError,
    DomainError,
    ExchangeRateUnavailableError,
    IdempotencyConflictError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    NotFoundError,
    PaymentFailedError,
    UnauthorizedError,
    ValidationFailedError,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CartExpiredError",
    "DomainError",
    "ExchangeRateUnavailableError",
    "IdempotencyConflictError",
    "InsufficientStockError",
    "InvalidStatusTransitionError",
    "NotFoundError",
    "PaymentFailedError",
    "UnauthorizedError",
    "ValidationFailedError",
    "error_body",
    "register_exception_handlers",
]


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        simplified = [
            {
                "loc": [str(part) for part in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(
                "VALIDATION_FAILED", "request payload is invalid", {"errors": simplified}
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "internal error"),
        )
