"""Currency lookups, FX conversion and rate refresh.

``refresh_rates`` only ever writes rows a successful fetch produced. A failing
provider raises and leaves the previously stored rates untouched, so pricing
degrades to "slightly stale" instead of "broken".
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ExchangeRateUnavailableError
from app.domain.currency.models import Currency
from app.domain.currency.money import default_decimal_places, round_money
from app.domain.currency.repository import CurrencyRepository
from app.integrations.exchange_rate import ExchangeRateProvider, get_exchange_rate_provider


class CurrencyService:
    def __init__(
        self,
        session: AsyncSession,
        provider: ExchangeRateProvider | None = None,
    ) -> None:
        self.session = session
        self._repo = CurrencyRepository(session)
        self._provider = provider or get_exchange_rate_provider()

    async def list_active(self) -> list[Currency]:
        return await self._repo.list_active()

    async def decimal_places(self, code: str) -> int:
        currency = await self._repo.get(code)
        if currency is not None:
            return currency.decimal_places
        return default_decimal_places(code)

    async def convert(self, amount: Decimal, from_code: str, to_code: str) -> Decimal:
        source = from_code.upper()
        target = to_code.upper()
        places = await self.decimal_places(target)

        if source == target:
            return round_money(amount, target, places)

        direct = await self._repo.get_rate(source, target)
        if direct is not None:
            return round_money(amount * direct.rate, target, places)

        inverse = await self._repo.get_rate(target, source)
        if inverse is not None and inverse.rate != 0:
            return round_money(amount / inverse.rate, target, places)

        raise ExchangeRateUnavailableError(
            message=f"no exchange rate available for {source}->{target}",
            details={"base": source, "quote": target},
        )

    async def refresh_rates(self, base: str) -> int:
        """Pull rates quoted against ``base`` and persist the ones we track."""
        base_code = base.upper()
        rates = await self._provider.fetch(base_code)

        updated = 0
        for quote_code, rate in rates.items():
            quote = quote_code.upper()
            if quote == base_code:
                continue
            if await self._repo.get(quote) is None:
                continue
            await self._repo.upsert_rate(base_code, quote, rate, self._provider.name)
            updated += 1

        await self.session.flush()
        return updated
