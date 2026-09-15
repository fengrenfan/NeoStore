from __future__ import annotations

import pytest

from app.domain.catalog.service import CatalogService
from app.domain.region.service import RegionService
from tests.factories import seed_product, seed_world

pytestmark = pytest.mark.anyio


async def test_get_product_by_slug_returns_requested_locale(db_session):
    await seed_world(db_session)
    detail = await CatalogService(db_session).get_product_by_slug("neon-tee", "en")

    assert detail.name == "Neon Tee"
    assert detail.slug == "neon-tee"
    assert detail.status == "published"
    assert detail.media[0].url == "https://cdn.example.com/neon.jpg"
    assert detail.variants[0].sku == "NEON-001"
    assert detail.variants[0].available == 10


async def test_get_product_by_slug_falls_back_to_default_locale(db_session):
    product = await seed_world(db_session)
    # Add a second product that only exists in zh-CN.
    await seed_product(
        db_session,
        name_en="Only Chinese",
        name_zh="仅中文商品",
        slug="zh-only",
        sku="ZH-001",
        locales=["zh-CN"],
    )

    detail = await CatalogService(db_session).get_product_by_slug("zh-only", "en")
    assert detail.name == "仅中文商品"
    assert detail.id is not None
    assert product.id != detail.id


async def test_locale_without_translation_uses_default_text(db_session):
    await seed_world(db_session)
    detail = await CatalogService(db_session).get_product_by_slug("neon-tee", "ja")
    assert detail.name == "霓虹 T 恤"


async def test_unknown_slug_raises_not_found(db_session):
    from app.core.domain_errors import NotFoundError

    await seed_world(db_session)
    with pytest.raises(NotFoundError) as exc:
        await CatalogService(db_session).get_product_by_slug("nope", "en")
    assert exc.value.code == "PRODUCT_NOT_FOUND"


async def test_draft_products_are_not_listed(db_session):
    await seed_world(db_session)
    await seed_product(
        db_session,
        name_en="Hidden",
        name_zh="隐藏商品",
        slug="hidden",
        sku="HID-001",
        status="draft",
    )

    cards, total = await CatalogService(db_session).list_products(locale="en")

    assert total == 1
    assert [card.slug for card in cards] == ["neon-tee"]


async def test_list_products_converts_to_region_currency(db_session):
    await seed_world(db_session)
    region = await RegionService(db_session).resolve_region("cn")

    cards, _ = await CatalogService(db_session).list_products(locale="en", region=region)

    assert cards[0].currency == "CNY"
    # 19.99 USD * 7.25 = 144.9275 → 144.93
    assert str(cards[0].price) == "144.93"


async def test_pagination_reports_the_full_count(db_session):
    await seed_world(db_session)
    for index in range(3):
        await seed_product(
            db_session,
            name_en=f"Extra {index}",
            name_zh=f"额外 {index}",
            slug=f"extra-{index}",
            sku=f"EXTRA-{index}",
        )

    page, total = await CatalogService(db_session).list_products(locale="en", limit=2, offset=0)

    assert total == 4
    assert len(page) == 2
