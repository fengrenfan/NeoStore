"""Alembic environment.

The database URL comes from application settings (i.e. ``DATABASE_URL``), not
from ``alembic.ini``, so migrations and the app can never disagree about which
database they are talking to::

    alembic upgrade head
    DATABASE_URL=postgresql+asyncpg://... alembic upgrade head

Importing ``app.domain`` registers every model on ``Base.metadata`` before
autogenerate runs — without it, Alembic would happily generate a migration that
drops tables it cannot see.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.domain
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config

# Interpret the config file for Python logging. ``disable_existing_loggers`` is
# off so running migrations in-process (e.g. from a test) cannot silence the
# application's own loggers.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

app.domain.load_models()
target_metadata = Base.metadata

#: Settings win over whatever placeholder is in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
