from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.domain_errors import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.domain.cart.models import CartStatus
from app.domain.cart.service import CartService
from app.domain.inventory.service import InventoryService
from app.domain.order.service import OrderService
from app.domain.order.state_machine import OrderStatus, allowed_targets
from tests.factories import seed_product, seed_world

pytestmark = pytest.mark.anyio

SHIPPING = {
    "name": "Ada Lovelace",
    "line1": "1 Analytical Engine Way",
    "city": "London",
    "country": "GB",
    "postal_code": "EC1A",
}


async def _checkout_ready_cart(session, quantity: int = 1, **product_kwargs):
    """A published product plus a USD cart holding ``quantity`` of it."""
    product = await seed_world(session, **product_kwargs)
    carts = CartService(session)
    cart = await carts.create(region_code="us", currency_code="USD")
    await carts.add_line(cart.token, product.variants[0].id, quantity)
    return product, cart


async def test_checkout_turns_a_cart_into_an_awaiting_payment_order(db_session):
    product, cart = await _checkout_ready_cart(db_session)
    variant_id = product.variants[0].id

    order = await OrderService(db_session).checkout(
        cart_token=cart.token,
        email="ada@example.com",
        shipping_address=SHIPPING,
        locale="en",
    )

    assert order.status == OrderStatus.AWAITING_PAYMENT
    assert order.number.startswith("NS-")
    assert order.currency_code == "USD"
    assert order.total == Decimal("31.98")
    assert len(order.lines) == 1

    line = order.lines[0]
    assert line.sku == "NEON-001"
    assert line.product_name == "Neon Tee"  # resolved through the en translation
    assert line.unit_price == Decimal("19.99")
    assert line.line_total == Decimal("19.99")
    assert line.variant_id == variant_id

    # The cart is spent, and exactly one unit is now promised to the order.
    assert cart.status == CartStatus.CONVERTED
    assert cart.email == "ada@example.com"
    assert await InventoryService(db_session).available(variant_id) == 9


async def test_checkout_records_the_intent_on_the_event_trail(db_session):
    _product, cart = await _checkout_ready_cart(db_session)

    order = await OrderService(db_session).checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
    )

    assert [str(event.to_status) for event in order.events] == ["awaiting_payment"]
    assert order.events[0].note.startswith("intent:mock_")


async def test_checkout_is_idempotent_for_the_same_key(db_session):
    product, cart = await _checkout_ready_cart(db_session)
    variant_id = product.variants[0].id
    orders = OrderService(db_session)

    first = await orders.checkout(
        cart_token=cart.token,
        email="ada@example.com",
        shipping_address=SHIPPING,
        idempotency_key="key-123",
    )
    second = await orders.checkout(
        cart_token=cart.token,
        email="ada@example.com",
        shipping_address=SHIPPING,
        idempotency_key="key-123",
    )

    assert first.id == second.id
    # The retry must not have reserved a second unit.
    assert await InventoryService(db_session).available(variant_id) == 9


async def test_checkout_refuses_an_empty_cart(db_session):
    await seed_world(db_session)
    cart = await CartService(db_session).create(region_code="us", currency_code="USD")

    with pytest.raises(NotFoundError) as exc:
        await OrderService(db_session).checkout(
            cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
        )
    assert exc.value.code == "CART_EMPTY"


async def test_checkout_refuses_to_oversell(db_session):
    _product, cart = await _checkout_ready_cart(db_session, quantity=10)
    orders = OrderService(db_session)

    # Drain the remaining stock with a second cart.
    other_cart = await CartService(db_session).create(region_code="us", currency_code="USD")
    await CartService(db_session).add_line(
        other_cart.token, cart.lines[0].variant_id, 10
    )
    await orders.checkout(
        cart_token=other_cart.token, email="b@example.com", shipping_address=SHIPPING
    )

    second = await CartService(db_session).create(region_code="us", currency_code="USD")
    await CartService(db_session).add_line(second.token, cart.lines[0].variant_id, 1)

    with pytest.raises(InsufficientStockError):
        await orders.checkout(
            cart_token=second.token, email="c@example.com", shipping_address=SHIPPING
        )


async def test_pay_confirms_the_intent_and_commits_stock(db_session):
    product, cart = await _checkout_ready_cart(db_session)
    variant_id = product.variants[0].id
    orders = OrderService(db_session)
    order = await orders.checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
    )

    paid = await orders.pay(order.number)

    assert paid.status == OrderStatus.PAID
    inventory = InventoryService(db_session)
    # Reserved is released and the physical count actually drops.
    assert await inventory.available(variant_id) == 9
    item = await inventory._repo.get(variant_id)
    assert item.quantity == 9
    assert item.reserved == 0


async def test_full_lifecycle_reaches_completed(db_session):
    _product, cart = await _checkout_ready_cart(db_session)
    orders = OrderService(db_session)
    order = await orders.checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
    )

    await orders.pay(order.number)
    await orders.transition(order.number, OrderStatus.FULFILLED)
    done = await orders.transition(order.number, OrderStatus.COMPLETED)

    assert done.status == OrderStatus.COMPLETED
    assert [str(event.to_status) for event in done.events] == [
        "awaiting_payment",
        "paid",
        "fulfilled",
        "completed",
    ]


async def test_cancelling_releases_the_reservation(db_session):
    product, cart = await _checkout_ready_cart(db_session)
    variant_id = product.variants[0].id
    orders = OrderService(db_session)
    order = await orders.checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
    )
    assert await InventoryService(db_session).available(variant_id) == 9

    cancelled = await orders.transition(order.number, OrderStatus.CANCELLED, note="customer changed mind")

    assert cancelled.status == OrderStatus.CANCELLED
    assert await InventoryService(db_session).available(variant_id) == 10
    assert cancelled.events[-1].note == "customer changed mind"


async def test_illegal_transition_is_refused(db_session):
    _product, cart = await _checkout_ready_cart(db_session)
    orders = OrderService(db_session)
    order = await orders.checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
    )

    # awaiting_payment cannot jump straight to completed.
    with pytest.raises(InvalidStatusTransitionError):
        await orders.transition(order.number, OrderStatus.COMPLETED)

    assert allowed_targets(OrderStatus.AWAITING_PAYMENT) == ["cancelled", "paid"]


async def test_order_lines_are_a_snapshot_not_a_live_reference(db_session):
    product, cart = await _checkout_ready_cart(db_session)
    orders = OrderService(db_session)
    order = await orders.checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING, locale="en"
    )

    # Rename the product and re-price it after the order was placed.
    translation = next(t for t in product.translations if t.locale == "en")
    translation.name = "Renamed Tee"
    variant_id = product.variants[0].id
    from tests.factories import set_variant_price

    await set_variant_price(db_session, variant_id, "USD", Decimal("49.99"))

    reloaded = await orders.get(order.number)
    assert reloaded.lines[0].product_name == "Neon Tee"
    assert reloaded.lines[0].unit_price == Decimal("19.99")


async def test_order_can_be_found_by_number_or_id(db_session):
    _product, cart = await _checkout_ready_cart(db_session)
    orders = OrderService(db_session)
    order = await orders.checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
    )

    assert (await orders.get_by_ref(order.number)).id == order.id
    assert (await orders.get_by_ref(str(order.id))).id == order.id

    with pytest.raises(NotFoundError) as exc:
        await orders.get_by_ref("NS-000000-NOPE")
    assert exc.value.code == "ORDER_NOT_FOUND"


async def test_order_listing_reports_the_full_count(db_session):
    _product, cart = await _checkout_ready_cart(db_session)
    orders = OrderService(db_session)
    await orders.checkout(
        cart_token=cart.token, email="ada@example.com", shipping_address=SHIPPING
    )

    listed, total = await orders.list_orders()

    assert total == 1
    assert len(listed) == 1

    awaiting, awaiting_total = await orders.list_orders(status=OrderStatus.AWAITING_PAYMENT)
    assert awaiting_total == 1

    _none, paid_total = await orders.list_orders(status=OrderStatus.PAID)
    assert paid_total == 0


async def test_a_second_product_does_not_disturb_the_first_order(db_session):
    """Two orders in one session must not share lines through the identity map."""
    product_a, cart_a = await _checkout_ready_cart(db_session)
    product_b = await seed_product(
        db_session, name_en="Second", name_zh="第二件", slug="second", sku="SEC-001"
    )
    carts = CartService(db_session)
    cart_b = await carts.create(region_code="us", currency_code="USD")
    await carts.add_line(cart_b.token, product_b.variants[0].id, 2)

    orders = OrderService(db_session)
    order_a = await orders.checkout(
        cart_token=cart_a.token, email="a@example.com", shipping_address=SHIPPING, locale="en"
    )
    order_b = await orders.checkout(
        cart_token=cart_b.token, email="b@example.com", shipping_address=SHIPPING, locale="en"
    )

    assert [line.sku for line in order_a.lines] == ["NEON-001"]
    assert [line.sku for line in order_b.lines] == ["SEC-001"]
    assert order_b.lines[0].line_total == Decimal("39.98")
