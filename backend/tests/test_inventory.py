from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain_errors import InsufficientStockError, NotFoundError
from app.domain.inventory.models import InventoryItem
from app.domain.inventory.service import InventoryService
from tests.factories import seed_world

pytestmark = pytest.mark.anyio

requires_postgres = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="SELECT ... FOR UPDATE is a no-op on SQLite — run with TEST_DATABASE_URL to verify",
)


async def test_reserve_decreases_available(db_session):
    product = await seed_world(db_session)
    variant_id = product.variants[0].id
    service = InventoryService(db_session)

    assert await service.available(variant_id) == 10
    await service.reserve(variant_id, 4)

    assert await service.available(variant_id) == 6
    item = await db_session.get(InventoryItem, variant_id)
    assert item.quantity == 10
    assert item.reserved == 4


async def test_reserve_beyond_stock_is_rejected(db_session):
    product = await seed_world(db_session)
    service = InventoryService(db_session)

    with pytest.raises(InsufficientStockError) as exc:
        await service.reserve(product.variants[0].id, 999)

    assert exc.value.code == "INSUFFICIENT_STOCK"
    assert exc.value.details["available"] == 10


async def test_repeated_reserves_eventually_exhaust_stock(db_session):
    """Sequential guard check — the concurrency proof lives in the PG test below."""
    product = await seed_world(db_session)
    variant_id = product.variants[0].id
    service = InventoryService(db_session)

    for _ in range(10):
        await service.reserve(variant_id, 1)

    assert await service.available(variant_id) == 0
    with pytest.raises(InsufficientStockError):
        await service.reserve(variant_id, 1)


async def test_release_returns_reserved_units(db_session):
    product = await seed_world(db_session)
    variant_id = product.variants[0].id
    service = InventoryService(db_session)

    await service.reserve(variant_id, 5)
    await service.release(variant_id, 5)

    assert await service.available(variant_id) == 10


async def test_commit_reservation_deducts_physical_stock(db_session):
    product = await seed_world(db_session)
    variant_id = product.variants[0].id
    service = InventoryService(db_session)

    await service.reserve(variant_id, 3)
    await service.commit_reservation(variant_id, 3)

    item = await db_session.get(InventoryItem, variant_id)
    assert item.quantity == 7
    assert item.reserved == 0
    assert await service.available(variant_id) == 7


async def test_adjust_rejects_dropping_below_reserved(db_session):
    product = await seed_world(db_session)
    variant_id = product.variants[0].id
    service = InventoryService(db_session)

    await service.reserve(variant_id, 8)
    with pytest.raises(InsufficientStockError):
        await service.adjust(variant_id, -5)

    item = await service.adjust(variant_id, +2)
    assert item.quantity == 12


async def test_reserve_without_stock_record_is_rejected(db_session):
    with pytest.raises(InsufficientStockError):
        await InventoryService(db_session).reserve(uuid.uuid4(), 1)


async def test_release_without_stock_record_raises(db_session):
    with pytest.raises(NotFoundError):
        await InventoryService(db_session).release(uuid.uuid4(), 1)


@requires_postgres
async def test_concurrent_reserves_never_oversell(engine, anyio_backend):
    """20 concurrent single-unit reservations against 10 units of stock."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as setup:
        await setup.execute(__import__("sqlalchemy").text("DELETE FROM inventory_item"))
        variant_id = uuid.uuid4()
        setup.add(InventoryItem(variant_id=variant_id, quantity=10, reserved=0))
        await setup.commit()

    async def reserve_one() -> bool:
        async with factory() as session:
            try:
                await InventoryService(session).reserve(variant_id, 1)
                await session.commit()
                return True
            except InsufficientStockError:
                await session.rollback()
                return False

    outcomes = await asyncio.gather(*[reserve_one() for _ in range(20)])

    assert sum(outcomes) == 10
    async with factory() as check:
        item = await check.get(InventoryItem, variant_id)
        assert item.reserved == 10
        assert item.quantity == 10
