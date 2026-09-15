from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.domain_errors import ExchangeRateUnavailableError
from app.domain.currency.money import default_decimal_places, round_money
from app.domain.currency.service import CurrencyService
from app.integrations.exchange_rate import StaticRateProvider
from tests.factories import seed_currencies, seed_rates


class FailingProvider(StaticRateProvider):
    name = "failing"

    def __init__(self) -> None:
        super().__init__({})

    async def fetch(self, base: str) -> dict[str, Decimal]:
        raise ExchangeRateUnavailableError(message="provider is down")


def test_round_money_uses_half_up():
    assert round_money(Decimal("19.999"), "USD") == Decimal("20.00")
    assert round_money(Decimal("18.3908"), "EUR") == Decimal("18.39")
    assert round_money(Decimal("2.345"), "USD") == Decimal("2.35")


def test_zero_decimal_currency_has_no_cents():
    assert default_decimal_places("JPY") == 0
    assert round_money(Decimal("199.6"), "JPY") == Decimal("200")


@pytest.mark.anyio
async def test_convert_uses_stored_rate(db_session):
    await seed_currencies(db_session)
    await seed_rates(db_session)

    service = CurrencyService(db_session, StaticRateProvider({}))
    assert await service.convert(Decimal("100.00"), "USD", "CNY") == Decimal("725.00")


@pytest.mark.anyio
async def test_convert_uses_inverse_rate_when_only_reverse_exists(db_session):
    await seed_currencies(db_session)
    await seed_rates(db_session)

    service = CurrencyService(db_session, StaticRateProvider({}))
    # Only USD->CNY is stored; CNY->USD must divide by it.
    converted = await service.convert(Decimal("725.00"), "CNY", "USD")
    assert converted == Decimal("100.00")


@pytest.mark.anyio
async def test_convert_same_currency_is_identity_and_rounds(db_session):
    await seed_currencies(db_session)
    service = CurrencyService(db_session, StaticRateProvider({}))
    assert await service.convert(Decimal("5.005"), "USD", "USD") == Decimal("5.01")


@pytest.mark.anyio
async def test_convert_without_any_rate_raises(db_session):
    await seed_currencies(db_session)
    service = CurrencyService(db_session, StaticRateProvider({}))
    with pytest.raises(ExchangeRateUnavailableError):
        await service.convert(Decimal("10.00"), "EUR", "CNY")


@pytest.mark.anyio
async def test_refresh_rates_writes_only_tracked_currencies(db_session):
    await seed_currencies(db_session)
    provider = StaticRateProvider(
        {"CNY": Decimal("7.10"), "EUR": Decimal("0.92"), "ZZZ": Decimal("1.0")}
    )

    updated = await CurrencyService(db_session, provider).refresh_rates("USD")

    assert updated == 2  # ZZZ is not a tracked currency
    service = CurrencyService(db_session, StaticRateProvider({}))
    assert await service.convert(Decimal("1.00"), "USD", "CNY") == Decimal("7.10")


@pytest.mark.anyio
async def test_refresh_failure_keeps_previously_stored_rates(db_session):
    await seed_currencies(db_session)
    await seed_rates(db_session)

    with pytest.raises(ExchangeRateUnavailableError):
        await CurrencyService(db_session, FailingProvider()).refresh_rates("USD")

    service = CurrencyService(db_session, StaticRateProvider({}))
    assert await service.convert(Decimal("100.00"), "USD", "CNY") == Decimal("725.00")
