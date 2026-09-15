from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.domain_errors import CartExpiredError, NotFoundError
from app.domain.cart.models import CartStatus
from app.domain.cart.service import CartService
from app.domain.order.service import OrderService
from app.domain.region.service import RegionService
from tests.factories import seed_world

pytestmark = pytest.mark.anyio

TOKEN = "cart.unknown.token"


async def _cart_with_one_line(session):
    """One published product in a USD cart, one line of quantity 1."""
    product = await seed_world(session)
    variant_id = product.variants[0].id
    carts = CartService(session)
    cart = await carts.create(region_code="us", currency_code="USD")
    await carts.add_line(cart.token, variant_id, 1)
    return cart, variant_id


async def test_create_returns_active_cart_with_future_expiry(db_session):
    await seed_world(db_session)
    cart = await CartService(db_session).create(region_code="us", currency_code="usd")

    assert cart.token
    assert cart.status == CartStatus.ACTIVE
    assert cart.currency_code == "USD"  # normalised to upper case
    assert cart.expires_at > datetime.now(UTC) - timedelta(minutes=1)


async def test_add_line_snapshots_the_unit_price(db_session):
    cart, variant_id = await _cart_with_one_line(db_session)

    assert len(cart.lines) == 1
    line = cart.lines[0]
    assert line.variant_id == variant_id
    assert line.quantity == 1
    # 19.99 USD has an explicit-free base price, so no conversion happened.
    assert line.unit_price == Decimal("19.99")
    assert line.currency_code == "USD"


async def test_adding_the_same_variant_merges_into_one_line(db_session):
    product = await seed_world(db_session)
    variant_id = product.variants[0].id
    carts = CartService(db_session)
    cart = await carts.create(region_code="us", currency_code="USD")

    await carts.add_line(cart.token, variant_id, 2)
    cart = await carts.add_line(cart.token, variant_id, 3)

    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 5


async def test_update_line_rewrites_quantity_and_zero_removes_it(db_session):
    cart, _variant_id = await _cart_with_one_line(db_session)
    carts = CartService(db_session)
    line_id = cart.lines[0].id

    cart = await carts.update_line(cart.token, line_id, 7)
    assert cart.lines[0].quantity == 7

    cart = await carts.update_line(cart.token, line_id, 0)
    assert cart.lines == []


async def test_remove_line_empties_the_cart(db_session):
    cart, _variant_id = await _cart_with_one_line(db_session)
    carts = CartService(db_session)

    cart = await carts.remove_line(cart.token, cart.lines[0].id)

    assert cart.lines == []


async def test_totals_add_shipping_and_tax(db_session):
    cart, _variant_id = await _cart_with_one_line(db_session)

    breakdown = await CartService(db_session).totals(cart.token)

    # 19.99 subtotal is under the 100 threshold, so flat 9.90 shipping applies.
    assert breakdown.subtotal == Decimal("19.99")
    assert breakdown.shipping_fee == Decimal("9.90")
    # (19.99 + 9.90) * 0.07 = 2.0923 -> 2.09
    assert breakdown.tax == Decimal("2.09")
    assert breakdown.total == Decimal("31.98")


async def test_totals_use_the_cart_region_not_the_callers(db_session):
    """A CN cart keeps CN tax even when nothing about the caller says "cn"."""
    product = await seed_world(db_session)
    carts = CartService(db_session)
    cart = await carts.create(region_code="cn", currency_code="CNY")
    await carts.add_line(cart.token, product.variants[0].id, 1)

    # The US region is resolvable and taxes 7%; the CN cart must ignore it.
    us_region = await RegionService(db_session).resolve_region("us")
    assert us_region.tax_rate == Decimal("0.0700")

    breakdown = await carts.totals(cart.token)

    assert breakdown.currency == "CNY"
    # 19.99 USD converts to 144.93 CNY; 6% of that is 8.70 (HALF_UP), not 7%.
    assert breakdown.subtotal == Decimal("144.93")
    assert breakdown.tax == Decimal("8.70")


async def test_cart_totals_match_the_order_they_become(db_session):
    """The number shown in the cart is the number the order is created with."""
    product = await seed_world(db_session)
    carts = CartService(db_session)
    cart = await carts.create(region_code="cn", currency_code="CNY")
    await carts.add_line(cart.token, product.variants[0].id, 2)

    breakdown = await carts.totals(cart.token)
    order = await OrderService(db_session).checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address={}
    )

    assert order.currency_code == "CNY"
    assert (order.subtotal, order.shipping_fee, order.tax, order.total) == (
        breakdown.subtotal,
        breakdown.shipping_fee,
        breakdown.tax,
        breakdown.total,
    )


async def test_free_shipping_kicks_in_above_the_threshold(db_session):
    product = await seed_world(db_session, base_price=Decimal("120.00"))
    variant_id = product.variants[0].id
    carts = CartService(db_session)
    cart = await carts.create(region_code="us", currency_code="USD")
    await carts.add_line(cart.token, variant_id, 1)

    breakdown = await carts.totals(cart.token)

    assert breakdown.shipping_fee == Decimal("0.00")


async def test_non_positive_quantity_is_rejected(db_session):
    product = await seed_world(db_session)
    carts = CartService(db_session)
    cart = await carts.create(region_code="us", currency_code="USD")

    with pytest.raises(NotFoundError) as exc:
        await carts.add_line(cart.token, product.variants[0].id, 0)
    assert exc.value.code == "INVALID_QUANTITY"


async def test_unknown_variant_is_rejected(db_session):
    import uuid

    await seed_world(db_session)
    carts = CartService(db_session)
    cart = await carts.create(region_code="us", currency_code="USD")

    with pytest.raises(NotFoundError) as exc:
        await carts.add_line(cart.token, uuid.uuid4(), 1)
    assert exc.value.code == "VARIANT_NOT_FOUND"


async def test_unknown_token_is_not_found(db_session):
    await seed_world(db_session)

    with pytest.raises(NotFoundError) as exc:
        await CartService(db_session).get_by_token(TOKEN)
    assert exc.value.code == "CART_NOT_FOUND"


async def test_expired_cart_is_refused(db_session):
    cart, _variant_id = await _cart_with_one_line(db_session)
    cart.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    with pytest.raises(CartExpiredError):
        await CartService(db_session).get_by_token(cart.token)


async def test_converted_cart_is_refused(db_session):
    cart, _variant_id = await _cart_with_one_line(db_session)
    carts = CartService(db_session)

    await carts.mark_converted(cart)

    with pytest.raises(CartExpiredError) as exc:
        await carts.get_by_token(cart.token)
    # 410 Gone: the cart still exists but can no longer be used.
    assert exc.value.status_code == 410
    assert exc.value.details["status"] == "converted"
