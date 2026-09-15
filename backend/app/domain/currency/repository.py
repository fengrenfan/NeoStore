from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.currency.models import Currency, ExchangeRate


class CurrencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, code: str) -> Currency | None:
        return await self.session.get(Currency, code.upper())

    async def list_active(self) -> list[Currency]:
        stmt = select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.code)
        return list((await self.session.execute(stmt)).scalars())

    async def get_rate(self, base: str, quote: str) -> ExchangeRate | None:
        return await self.session.get(ExchangeRate, (base.upper(), quote.upper()))

    async def list_rates(self, base: str) -> list[ExchangeRate]:
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.base_code == base.upper())
            .order_by(ExchangeRate.quote_code)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def upsert_rate(
        self, base: str, quote: str, rate: Decimal, source: str
    ) -> ExchangeRate:
        existing = await self.get_rate(base, quote)
        if existing is None:
            row = ExchangeRate(
                base_code=base.upper(),
                quote_code=quote.upper(),
                rate=rate,
                source=source,
            )
            self.session.add(row)
            await self.session.flush()
            return row
        existing.rate = rate
        existing.source = source
        existing.fetched_at = func.now()
        await self.session.flush()
        return existing

    async def upsert_currency(self, currency: Currency) -> Currency:
        existing = await self.session.get(Currency, currency.code.upper())
        if existing is None:
            self.session.add(currency)
            await self.session.flush()
            return currency
        existing.name = currency.name
        existing.symbol = currency.symbol
        existing.decimal_places = currency.decimal_places
        existing.is_active = currency.is_active
        await self.session.flush()
        return existing
