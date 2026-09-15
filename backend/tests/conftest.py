"""Shared pytest fixtures.

Database resolution:

1. ``TEST_DATABASE_URL`` — point this at a real PostgreSQL to exercise the
   production dialect end to end (see ``docs/RUNBOOK.md``). The target database
   is wiped and rebuilt before every test, so never point it at anything you
   care about.
2. Otherwise SQLite in-memory, which keeps the local loop instant.

Two deliberate choices worth knowing about:

* The engine is **function scoped**. anyio runs every async test on a fresh
  event loop, and an engine built on loop A cannot be used from loop B —
  ``aiosqlite``/``asyncpg`` connections simply stall. Building one engine per
  test keeps every connection and its loop together.
* Schema is created fresh per test rather than wrapping tests in a transaction
  that gets rolled back. Route handlers call ``session.commit()``, and a
  savepoint-based fixture would silently let those commits escape the rollback
  and leak rows into the next test.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.domain  # noqa: F401  (registers model modules)
from app.db.base import Base
from app.db.session import build_engine, get_session


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.getenv("TEST_DATABASE_URL") or "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def dialect(database_url: str) -> str:
    return "postgresql" if database_url.startswith("postgresql") else "sqlite"


@pytest.fixture
async def engine(database_url: str, anyio_backend: str):
    """A private engine whose schema is rebuilt for every single test."""
    app.domain.load_models()
    eng = build_engine(database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
def session_factory(engine):
    """Factory for tests that need genuinely concurrent sessions."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(engine):
    """A request-like session. Commits are real, but the schema is thrown away."""
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
async def client(db_session):
    from app.main import create_app

    application = create_app()

    async def _override():
        yield db_session

    application.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    application.dependency_overrides.clear()
