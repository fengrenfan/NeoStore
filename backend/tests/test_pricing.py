from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.domain.catalog.models import ProductVariant
from app.domain.pricing.schemas import LineInput
from app.domain.pricing.service import PricingService
from app.domain.region.service import RegionService
from tests.factories import seed_world, set_variant_price

pytestmark = pytest.mark.anyio


async def test_explicit_variant_price_beats_base_price(db_session):
    product = await seed_world(db_session)
    variant_id = product.variants[0].id
    await set_variant_price(db_session, variant_id, "USD", Decimal("19.99"))

    product.base_price = Decimal("100.00")
    await db_session.flush()

    variant = await db_session.get(ProductVariant, variant_id)
    assert await PricingService(db_session).unit_price(variant, "USD") == Decimal("19.99")


async def test_missing_variant_price_converts_and_rounds(db_session):
    product = await seed_world(db_session)
    variant = await db_session.get(ProductVariant, product.variants[0].id)

    # base price 19.99 USD, 1 USD = 0.92 EUR → 18.3908 → 18.39
    assert await PricingService(db_session).unit_price(variant, "EUR") == Decimal("18.39")


async def test_calculate_produces_consistent_totals(db_session):
    product = await seed_world(db_session)
    region = await RegionService(db_session).resolve_region("us")

    breakdown = await PricingService(db_session).calculate(
        [LineInput(variant_id=product.variants[0].id, quantity=2)],
        region=region,
        currency_code="USD",
    )

    assert breakdown.currency == "USD"
    assert breakdown.subtotal == Decimal("39.98")
    assert breakdown.shipping_fee == Decimal("9.90")  # below the free-shipping threshold
    assert breakdown.tax == Decimal("3.49")  # (39.98 + 9.90) * 7% = 3.4916
    assert breakdown.total == breakdown.subtotal + breakdown.shipping_fee + breakdown.tax


async def test_shipping_is_free_above_the_threshold(db_session):
    product = await seed_world(db_session, base_price=Decimal("60.00"))
    region = await RegionService(db_session).resolve_region("us")

    breakdown = await PricingService(db_session).calculate(
        [LineInput(variant_id=product.variants[0].id, quantity=2)],
        region=region,
        currency_code="USD",
    )

    assert breakdown.subtotal == Decimal("120.00")
    assert breakdown.shipping_fee == Decimal("0.00")


async def test_unknown_variant_is_skipped_not_crashing(db_session):
    await seed_world(db_session)
    region = await RegionService(db_session).resolve_region("us")

    breakdown = await PricingService(db_session).calculate(
        [LineInput(variant_id=uuid.uuid4(), quantity=1)],
        region=region,
        currency_code="USD",
    )
    assert breakdown.subtotal == Decimal("0.00")
    assert breakdown.total == breakdown.shipping_fee + breakdown.tax


async def test_amounts_are_decimal_not_float(db_session):
    product = await seed_world(db_session)
    region = await RegionService(db_session).resolve_region("us")

    breakdown = await PricingService(db_session).calculate(
        [LineInput(variant_id=product.variants[0].id, quantity=1)],
        region=region,
        currency_code="USD",
    )
    assert isinstance(breakdown.total, Decimal)
