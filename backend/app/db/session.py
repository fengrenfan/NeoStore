"""Async engine, session factory and connectivity probes."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def build_engine(url: str | None = None) -> AsyncEngine:
    """Create an engine, applying SQLite-specific pooling when needed.

    SQLite in-memory databases only live as long as their connection, so the
    pool must hand the same connection back every time.
    """
    target = url or settings.database_url
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if target.startswith("sqlite"):
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_async_engine(target, **kwargs)


engine = build_engine()
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session."""
    async with async_session_factory() as session:
        yield session


async def ping_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - probe must never raise
        return False


async def dispose_engine() -> None:
    await engine.dispose()
