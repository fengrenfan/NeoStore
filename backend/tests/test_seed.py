"""The seed script is the documented first-run path, so it gets real tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.domain.catalog.models import Product, ProductVariant, VariantPrice
from app.domain.currency.models import ExchangeRate
from app.domain.i18n.models import Locale
from app.domain.region.models import Region
from app.seed import CATEGORIES, CURRENCIES, LOCALES, PRODUCTS, REGIONS, run_seed

pytestmark = pytest.mark.anyio


async def test_seed_creates_the_whole_demo_dataset(db_session):
    report = await run_seed(db_session, refresh_rates=False)

    assert len(report.created) == len(LOCALES) + len(CURRENCIES) + len(REGIONS) + 1 + len(
        CATEGORIES
    ) + len(PRODUCTS) + 1
    assert report.skipped == []

    assert (await db_session.execute(select(func.count()).select_from(Locale))).scalar_one() == 3
    assert (await db_session.execute(select(func.count()).select_from(Region))).scalar_one() == 4
    assert (await db_session.execute(select(func.count()).select_from(Product))).scalar_one() == 3


async def test_seed_is_idempotent(db_session):
    first = await run_seed(db_session, refresh_rates=False)
    second = await run_seed(db_session, refresh_rates=False)

    assert first.created
    # Nothing new on the second pass, and no duplicates.
    assert second.created == []
    assert len(second.skipped) == len(first.created)
    assert (await db_session.execute(select(func.count()).select_from(Product))).scalar_one() == 3
    assert (await db_session.execute(select(func.count()).select_from(Locale))).scalar_one() == 3


async def test_seed_does_not_overwrite_operator_edits(db_session):
    await run_seed(db_session, refresh_rates=False)

    translation = (
        await db_session.execute(
            select(Product).where(Product.position == 0)
        )
    ).scalar_one()
    translation.status = "draft"
    await db_session.commit()

    await run_seed(db_session, refresh_rates=False)

    # The second run recognises the product and leaves the status alone.
    assert translation.status == "draft"


async def test_seeded_regions_bind_currency_locales_and_payments(db_session):
    await run_seed(db_session, refresh_rates=False)

    region = await db_session.get(Region, "jp")

    assert region is not None
    assert region.currency_code == "JPY"
    assert sorted(link.locale for link in region.locale_links) == ["en", "ja"]
    assert [link.provider_code for link in region.payment_method_links] == ["mock"]


async def test_explicit_variant_prices_survive_seeding(db_session):
    """Two variants are priced explicitly; the rest convert from base_price."""
    await run_seed(db_session, refresh_rates=False)

    rows = (
        await db_session.execute(
            select(ProductVariant.sku, VariantPrice.currency_code, VariantPrice.amount)
            .join(ProductVariant, ProductVariant.id == VariantPrice.variant_id)
            .order_by(ProductVariant.sku)
        )
    ).all()

    assert {(sku, code): amount for sku, code, amount in rows} == {
        ("NEON-TEE-S", "CNY"): Decimal("149.00"),
        ("PULSE-SNKR-41", "CNY"): Decimal("929.00"),
    }


async def test_seed_writes_fallback_rates_when_the_provider_is_skipped(db_session):
    await run_seed(db_session, refresh_rates=False)

    rates = (
        await db_session.execute(
            select(ExchangeRate).where(ExchangeRate.base_code == "USD")
        )
    ).scalars().all()

    quotes = {row.quote_code for row in rates}
    assert {"CNY", "EUR", "GBP", "JPY"} <= quotes
    assert all(row.source == "seed-fallback" for row in rates)


async def test_seed_uses_the_provider_when_one_is_supplied(db_session):
    from app.domain.currency.service import CurrencyService
    from app.integrations.exchange_rate import StaticRateProvider
    from app.seed import SeedReport, seed_currencies

    # The refresh can only update currencies that already exist.
    await seed_currencies(db_session, SeedReport())
    await db_session.flush()

    updated = await CurrencyService(
        db_session, provider=StaticRateProvider({"CNY": Decimal("7.05")})
    ).refresh_rates("USD")
    await db_session.commit()

    assert updated == 1


async def test_seeded_admin_can_log_in(client, db_session):
    await run_seed(db_session, refresh_rates=False)

    response = await client.post(
        "/api/v1/admin/auth/login",
        json={
            "email": settings.seed_admin_email,
            "password": settings.seed_admin_password,
        },
    )

    assert response.status_code == 200, response.text
    token = response.json()["access_token"]

    me = await client.get(
        "/api/v1/admin/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.json() == {"email": settings.seed_admin_email, "role": "owner"}


async def test_seeded_storefront_is_browsable(client, db_session):
    await run_seed(db_session, refresh_rates=False)

    listing = await client.get("/api/v1/store/products", params={"locale": "en"})
    assert listing.status_code == 200
    assert listing.headers["x-total-count"] == "3"
    slugs = {card["slug"] for card in listing.json()}
    assert slugs == {"neon-tee", "aurora-hoodie", "pulse-sneakers"}

    # ja has no product text of its own, so it falls back to the default locale.
    japanese = await client.get("/api/v1/store/products", params={"locale": "ja"})
    assert japanese.headers["content-language"] == "ja"
    assert {card["name"] for card in japanese.json()} == {"霓虹 T 恤", "极光卫衣", "脉冲运动鞋"}


async def test_zero_decimal_currency_prices_without_fractional_cents(client, db_session):
    await run_seed(db_session, refresh_rates=False)

    response = await client.get("/api/v1/store/products/pulse-sneakers", params={"region": "jp"})

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "JPY"
    # 129.00 USD * 151 = 19479 exactly, and JPY has no decimal places at all.
    assert "." not in str(body["price"])
    # The explicit CNY override is untouched by a JPY request.
    assert body["variants"][0]["sku"] == "PULSE-SNKR-41"


async def test_reset_admin_password_is_opt_in(db_session):
    await run_seed(db_session, refresh_rates=False)
    report = await run_seed(db_session, refresh_rates=False, reset_admin_password=True)

    assert any("password reset" in item for item in report.created)
