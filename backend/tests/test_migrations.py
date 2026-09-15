"""Migrations must describe exactly the schema the models describe.

Alembic drift is the kind of bug that only shows up on deploy day, so it is
checked here instead: apply every migration to an empty database, then compare
the resulting tables and columns against ``Base.metadata``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

import app.domain
from alembic import command
from app.core.config import settings
from app.db.base import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]

#: Alembic's own bookkeeping table; not part of the domain schema.
ALEMBIC_TABLE = "alembic_version"


@pytest.fixture
def migrated_database(monkeypatch):
    """Run ``alembic upgrade head`` against a throwaway SQLite file."""
    with tempfile.TemporaryDirectory() as workspace:
        db_path = Path(workspace) / "migrated.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        # env.py takes the URL from settings, so this is the knob that matters.
        monkeypatch.setattr(settings, "database_url", url)

        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            yield engine
        finally:
            engine.dispose()


def test_migrations_apply_from_scratch(migrated_database):
    tables = set(inspect(migrated_database).get_table_names())

    assert ALEMBIC_TABLE in tables
    assert len(tables) > 1


def test_migrated_schema_matches_the_models(migrated_database):
    app.domain.load_models()
    inspector = inspect(migrated_database)

    migrated = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in inspector.get_table_names()
        if table != ALEMBIC_TABLE
    }
    expected = {
        table.name: {column.name for column in table.columns}
        for table in Base.metadata.sorted_tables
    }

    assert set(migrated) == set(expected), "table set differs"
    for table in sorted(expected):
        assert migrated[table] == expected[table], f"columns differ for {table}"


def test_migrated_indexes_match_the_models(migrated_database):
    inspector = inspect(migrated_database)

    migrated = {
        (table, index["name"])
        for table in inspector.get_table_names()
        if table != ALEMBIC_TABLE
        for index in inspector.get_indexes(table)
    }
    expected = {
        (table.name, index.name)
        for table in Base.metadata.sorted_tables
        for index in table.indexes
    }

    assert expected <= migrated, f"missing indexes: {sorted(expected - migrated)}"


def test_downgrade_returns_to_an_empty_schema(migrated_database):
    """The migration is reversible, so a bad deploy can be rolled back."""
    db_path = migrated_database.url.database

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.downgrade(config, "base")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        remaining = set(inspect(engine).get_table_names()) - {ALEMBIC_TABLE}
    finally:
        engine.dispose()

    assert remaining == set()
