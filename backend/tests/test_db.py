import pytest
from sqlalchemy import text

from app.db.base import Base


@pytest.mark.anyio
async def test_session_round_trip(db_session):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


def test_metadata_uses_stable_naming_convention():
    convention = Base.metadata.naming_convention
    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"


@pytest.mark.anyio
async def test_money_and_rate_types_are_numeric():
    from app.db.base import Money, Rate

    assert Money.precision == 14 and Money.scale == 4
    assert Rate.precision == 20 and Rate.scale == 10
