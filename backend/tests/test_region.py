from __future__ import annotations

import pytest

from app.core.domain_errors import NotFoundError
from app.domain.region.service import RegionService
from tests.factories import seed_regions

pytestmark = pytest.mark.anyio


async def test_resolve_region_falls_back_to_default(db_session):
    await seed_regions(db_session)
    service = RegionService(db_session)

    assert (await service.resolve_region("XX")).code == "us"
    assert (await service.resolve_region(None)).code == "us"
    assert (await service.resolve_region("cn")).code == "cn"


async def test_region_carries_currency_locales_and_payments(db_session):
    await seed_regions(db_session)
    service = RegionService(db_session)

    region = await service.resolve_region("cn")
    assert region.currency_code == "CNY"
    assert await service.locales_for("cn") == ["zh-CN"]
    assert await service.available_payment_methods("cn") == []

    us = await service.resolve_region("us")
    assert us.is_default is True
    assert sorted(await service.locales_for("us")) == ["en", "zh-CN"]
    assert await service.available_payment_methods("us") == ["mock"]


async def test_no_region_configured_raises(db_session):
    with pytest.raises(NotFoundError) as exc:
        await RegionService(db_session).resolve_region(None)
    assert exc.value.code == "NO_REGION_CONFIGURED"
