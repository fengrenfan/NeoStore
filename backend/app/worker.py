"""arq worker: keeps exchange rates fresh on a schedule.

Run alongside the API::

    arq app.worker.WorkerSettings

The API never fetches rates on the request path — pricing reads whatever is
stored, and this job is what keeps that store current. If the provider is down
the previously stored rates stay in place, so the worst case is stale pricing
rather than a broken checkout.
"""

from __future__ import annotations

import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.db.session import async_session_factory, dispose_engine, ping_db
from app.domain.currency.service import CurrencyService

logger = logging.getLogger("neostore.worker")

BASE_CURRENCY = settings.default_currency.upper()

#: Guard against a misconfigured 0 turning the cron into 24 daily runs.
REFRESH_HOURS = max(1, settings.exchange_rate_refresh_hours)
#: Hours of the day the refresh fires, derived from the configured interval.
REFRESH_HOURS_OF_DAY = list(range(0, 24, REFRESH_HOURS))


async def refresh_exchange_rates(ctx: dict[str, Any]) -> int:
    """Pull the latest rates for every tracked currency."""
    async with async_session_factory() as session:
        updated = await CurrencyService(session).refresh_rates(BASE_CURRENCY)
        await session.commit()

    logger.info("refreshed %s exchange rates against %s", updated, BASE_CURRENCY)
    return updated


async def on_startup(ctx: dict[str, Any]) -> None:
    logger.info(
        "worker ready: refreshing %s every %sh at %s",
        BASE_CURRENCY,
        REFRESH_HOURS,
        ", ".join(f"{hour:02d}:00" for hour in REFRESH_HOURS_OF_DAY),
    )
    logger.info("database reachable: %s", await ping_db())


async def on_shutdown(ctx: dict[str, Any]) -> None:
    await dispose_engine()


class WorkerSettings:
    """Entry point referenced by ``arq app.worker.WorkerSettings``."""

    functions = [refresh_exchange_rates]
    cron_jobs = [
        cron(
            refresh_exchange_rates,
            hour=set(REFRESH_HOURS_OF_DAY),
            minute=0,
            # The first refresh waits for the schedule instead of hammering the
            # provider on every deploy.
            run_at_startup=False,
        )
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_tries = 3
    job_timeout = 120
    keep_result = 3600
