"""Money rounding — deliberately DB-free so any layer can call it safely."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

#: Currencies whose smallest unit is not 1/100. Anything else defaults to 2.
ZERO_DECIMAL_CURRENCIES = frozenset({"JPY", "KRW", "VND", "CLP", "ISK", "HUF"})
THREE_DECIMAL_CURRENCIES = frozenset({"BHD", "JOD", "KWD", "OMR", "TND"})

DEFAULT_DECIMAL_PLACES = 2


def default_decimal_places(code: str) -> int:
    upper = code.upper()
    if upper in ZERO_DECIMAL_CURRENCIES:
        return 0
    if upper in THREE_DECIMAL_CURRENCIES:
        return 3
    return DEFAULT_DECIMAL_PLACES


def round_money(
    amount: Decimal, code: str, decimal_places: int | None = None
) -> Decimal:
    """Round ``amount`` to the currency's precision using ROUND_HALF_UP.

    Passing ``decimal_places`` lets the caller use the value stored in the
    ``currency`` table instead of the built-in default.
    """
    places = default_decimal_places(code) if decimal_places is None else decimal_places
    quantizer = Decimal(1).scaleb(-places)
    return amount.quantize(quantizer, rounding=ROUND_HALF_UP)
