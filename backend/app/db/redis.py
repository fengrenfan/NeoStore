"""Redis client used for cart sessions, rate caching and the arq queue."""

from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import settings

redis_client: Redis = from_url(settings.redis_url, decode_responses=True)


async def ping_redis() -> bool:
    try:
        return bool(await redis_client.ping())
    except Exception:  # noqa: BLE001 - probe must never raise
        return False


async def close_redis() -> None:
    await redis_client.aclose()
