"""Exchange rate providers.

The provider contract is intentionally tiny so the data source can be swapped
without touching ``CurrencyService``. A failing fetch must never clear stored
rates — the service only writes what a successful fetch returns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import settings
from app.core.domain_errors import ExchangeRateUnavailableError


class ExchangeRateProvider(ABC):
    """Fetches rates quoted against ``base``."""

    name: str = "provider"

    @abstractmethod
    async def fetch(self, base: str) -> dict[str, Decimal]:
        """Return ``{quote_code: rate}`` where ``1 base == rate quote``."""


class OpenExchangeRateProvider(ExchangeRateProvider):
    """Adapter for open.er-api.com-style endpoints (``GET {base_url}/{base}``)."""

    name = "open-exchange-rate"

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def fetch(self, base: str) -> dict[str, Decimal]:
        params = {"api_key": self.api_key} if self.api_key else None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/{base}", params=params)
        except httpx.HTTPError as exc:
            raise ExchangeRateUnavailableError(
                message="exchange rate provider is unreachable",
                details={"base": base, "reason": exc.__class__.__name__},
            ) from exc

        if response.status_code != 200:
            raise ExchangeRateUnavailableError(
                message="exchange rate provider returned an error",
                details={"base": base, "status": response.status_code},
            )

        payload = response.json()
        raw_rates = payload.get("rates")
        if not isinstance(raw_rates, dict) or not raw_rates:
            raise ExchangeRateUnavailableError(
                message="exchange rate payload has no usable rates",
                details={"base": base},
            )

        rates: dict[str, Decimal] = {}
        for quote, value in raw_rates.items():
            try:
                rates[str(quote).upper()] = Decimal(str(value))
            except (InvalidOperation, ValueError):
                continue

        if not rates:
            raise ExchangeRateUnavailableError(
                message="exchange rate payload has no usable rates",
                details={"base": base},
            )
        return rates


class StaticRateProvider(ExchangeRateProvider):
    """Deterministic provider for tests and offline environments."""

    name = "static"

    def __init__(self, rates: dict[str, Decimal]) -> None:
        self._rates = {code.upper(): rate for code, rate in rates.items()}

    async def fetch(self, base: str) -> dict[str, Decimal]:
        return dict(self._rates)


def get_exchange_rate_provider() -> ExchangeRateProvider:
    return OpenExchangeRateProvider(
        base_url=settings.exchange_rate_api_url,
        api_key=settings.exchange_rate_api_key,
    )
