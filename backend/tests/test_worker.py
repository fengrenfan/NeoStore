"""The worker's schedule and job body."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app import worker
from app.domain.currency.repository import CurrencyRepository
from tests.factories import seed_currencies

pytestmark = pytest.mark.anyio


def test_schedule_follows_the_configured_interval(monkeypatch):
    # The module reads the interval at import time, so re-derive it here.
    monkeypatch.setattr(worker, "REFRESH_HOURS", 6)
    monkeypatch.setattr(worker, "REFRESH_HOURS_OF_DAY", list(range(0, 24, 6)))

    assert worker.REFRESH_HOURS_OF_DAY == [0, 6, 12, 18]


def test_a_zero_interval_cannot_become_an_hourly_stampede():
    assert worker.REFRESH_HOURS >= 1
    assert all(0 <= hour < 24 for hour in worker.REFRESH_HOURS_OF_DAY)


def test_cron_job_is_registered_once():
    assert len(worker.WorkerSettings.cron_jobs) == 1
    job = worker.WorkerSettings.cron_jobs[0]
    assert job.coroutine is worker.refresh_exchange_rates
    # arq keeps a bare int as-is and normalises an iterable into a set.
    assert job.minute == 0
    assert job.hour == set(worker.REFRESH_HOURS_OF_DAY)
    assert job.run_at_startup is False


async def test_refresh_job_writes_rates_and_reports_a_count(
    session_factory, monkeypatch
):
    """Runs the real job body against the test database."""
    from app.integrations.exchange_rate import StaticRateProvider

    async with session_factory() as setup:
        await seed_currencies(setup)
        await setup.commit()

    monkeypatch.setattr(
        "app.domain.currency.service.get_exchange_rate_provider",
        lambda: StaticRateProvider({"CNY": Decimal("7.33"), "JPY": Decimal("149.5")}),
    )
    monkeypatch.setattr(worker, "async_session_factory", session_factory)

    updated = await worker.refresh_exchange_rates({})

    assert updated == 2
    async with session_factory() as check:
        rates = await CurrencyRepository(check).list_rates("USD")
    written = {row.quote_code: row.rate for row in rates}
    assert written["CNY"] == Decimal("7.3300000000")
    assert written["JPY"] == Decimal("149.5000000000")
    assert all(row.source == "static" for row in rates)


async def test_refresh_job_leaves_stored_rates_alone_when_the_provider_fails(
    session_factory, monkeypatch
):
    from app.core.domain_errors import ExchangeRateUnavailableError

    async with session_factory() as setup:
        await seed_currencies(setup)
        await CurrencyRepository(setup).upsert_rate("USD", "CNY", Decimal("7.25"), "manual")
        await setup.commit()

    class Boom:
        name = "boom"

        async def fetch(self, base: str):
            raise ExchangeRateUnavailableError(message="provider is down")

    monkeypatch.setattr(
        "app.domain.currency.service.get_exchange_rate_provider", lambda: Boom()
    )
    monkeypatch.setattr(worker, "async_session_factory", session_factory)

    with pytest.raises(ExchangeRateUnavailableError):
        await worker.refresh_exchange_rates({})

    async with session_factory() as check:
        row = await CurrencyRepository(check).get_rate("USD", "CNY")
    assert row is not None
    assert row.rate == Decimal("7.2500000000")
    assert row.source == "manual"
