"""Storefront API surface, exercised through the real ASGI app."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.factories import seed_product, seed_world

pytestmark = pytest.mark.anyio

BASE = "/api/v1"
SHIPPING = {
    "name": "Ada Lovelace",
    "line1": "1 Analytical Engine Way",
    "city": "London",
    "country": "GB",
    "postal_code": "EC1A",
}


async def _published_variant_id(session) -> str:
    product = await seed_world(session)
    return str(product.variants[0].id)


async def test_list_locales_returns_the_seeded_registry(client, db_session):
    await seed_world(db_session)

    response = await client.get(f"{BASE}/store/locales")

    assert response.status_code == 200
    codes = [row["code"] for row in response.json()]
    assert codes == ["zh-CN", "en"]
    assert response.json()[0]["is_default"] is True


async def test_list_regions_includes_locales_and_payment_methods(client, db_session):
    await seed_world(db_session)

    response = await client.get(f"{BASE}/store/regions")

    assert response.status_code == 200
    us = next(row for row in response.json() if row["code"] == "us")
    assert us["currency_code"] == "USD"
    assert us["locales"] == ["en", "zh-CN"]
    assert us["payment_methods"] == ["mock"]


async def test_unknown_region_degrades_to_the_default(client, db_session):
    await seed_world(db_session)

    response = await client.get(f"{BASE}/store/products", params={"region": "atlantis"})

    assert response.status_code == 200
    assert response.headers["X-Currency"] == "USD"


async def test_product_list_honours_locale_and_region(client, db_session):
    await seed_world(db_session)

    response = await client.get(
        f"{BASE}/store/products", params={"locale": "en", "region": "cn"}
    )

    assert response.status_code == 200
    assert response.headers["content-language"] == "en"
    assert response.headers["x-currency"] == "CNY"
    assert response.headers["x-total-count"] == "1"
    card = response.json()[0]
    assert card["name"] == "Neon Tee"
    assert card["slug"] == "neon-tee"
    assert Decimal(card["price"]) == Decimal("144.93")


async def test_accept_language_beats_the_default_locale(client, db_session):
    await seed_world(db_session)

    response = await client.get(
        f"{BASE}/store/products", headers={"Accept-Language": "en-GB,en;q=0.9"}
    )

    assert response.headers["content-language"] == "en"
    assert response.json()[0]["name"] == "Neon Tee"


async def test_product_detail_exposes_variants_media_and_seo(client, db_session):
    await seed_world(db_session)

    response = await client.get(f"{BASE}/store/products/neon-tee", params={"locale": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Neon Tee"
    assert body["variants"][0]["sku"] == "NEON-001"
    assert body["variants"][0]["available"] == 10
    assert body["media"][0]["url"] == "https://cdn.example.com/neon.jpg"


async def test_unknown_slug_returns_the_error_envelope(client, db_session):
    await seed_world(db_session)

    response = await client.get(f"{BASE}/store/products/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_draft_products_are_invisible_to_the_storefront(client, db_session):
    await seed_world(db_session)
    await seed_product(
        db_session,
        name_en="Hidden",
        name_zh="隐藏",
        slug="hidden",
        sku="HID-001",
        status="draft",
    )

    listing = await client.get(f"{BASE}/store/products")
    detail = await client.get(f"{BASE}/store/products/hidden")

    assert listing.json() == [] or len(listing.json()) == 1
    assert detail.status_code == 404


async def test_cart_lifecycle_over_http(client, db_session):
    variant_id = await _published_variant_id(db_session)

    created = await client.post(f"{BASE}/store/carts", json={})
    assert created.status_code == 201
    cart = created.json()
    token = cart["token"]
    assert cart["currency_code"] == "USD"
    assert cart["lines"] == []
    assert client.cookies.get("neostore_cart") == token

    added = await client.post(
        f"{BASE}/store/carts/{token}/lines",
        json={"variant_id": variant_id, "quantity": 2},
    )
    assert added.status_code == 200
    lines = added.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["quantity"] == 2
    line_id = lines[0]["id"]

    totals = await client.get(f"{BASE}/store/carts/{token}/totals")
    assert totals.status_code == 200
    assert Decimal(totals.json()["subtotal"]) == Decimal("39.98")

    patched = await client.patch(
        f"{BASE}/store/carts/{token}/lines/{line_id}", json={"quantity": 5}
    )
    assert patched.json()["lines"][0]["quantity"] == 5

    removed = await client.delete(f"{BASE}/store/carts/{token}/lines/{line_id}")
    assert removed.json()["lines"] == []


async def test_cart_creation_can_pin_a_region(client, db_session):
    await seed_world(db_session)

    created = await client.post(f"{BASE}/store/carts", json={"region": "cn"})

    assert created.status_code == 201
    assert created.json()["region_code"] == "cn"
    assert created.json()["currency_code"] == "CNY"


async def test_a_carts_totals_ignore_the_requested_region(client, db_session):
    """The cart owns its region; ?region= must not re-tax someone else's basket."""
    variant_id = await _published_variant_id(db_session)
    token = (
        await client.post(f"{BASE}/store/carts", json={"region": "cn"})
    ).json()["token"]
    await client.post(
        f"{BASE}/store/carts/{token}/lines",
        json={"variant_id": variant_id, "quantity": 2},
    )

    own = await client.get(f"{BASE}/store/carts/{token}/totals")
    hijacked = await client.get(
        f"{BASE}/store/carts/{token}/totals", params={"region": "us"}
    )

    assert own.status_code == 200
    assert own.json() == hijacked.json()
    assert own.json()["currency"] == "CNY"
    # 2 * 144.93 = 289.86 subtotal, free shipping, 6% tax.
    assert Decimal(own.json()["tax"]) == Decimal("17.39")


async def test_adding_a_non_positive_quantity_is_a_validation_error(client, db_session):
    variant_id = await _published_variant_id(db_session)
    token = (await client.post(f"{BASE}/store/carts", json={})).json()["token"]

    response = await client.post(
        f"{BASE}/store/carts/{token}/lines",
        json={"variant_id": variant_id, "quantity": 0},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_unknown_cart_token_is_not_found(client, db_session):
    await seed_world(db_session)

    response = await client.get(f"{BASE}/store/carts/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CART_NOT_FOUND"


async def test_checkout_then_read_the_order_back(client, db_session):
    variant_id = await _published_variant_id(db_session)
    token = (await client.post(f"{BASE}/store/carts", json={})).json()["token"]
    await client.post(
        f"{BASE}/store/carts/{token}/lines",
        json={"variant_id": variant_id, "quantity": 1},
    )

    response = await client.post(
        f"{BASE}/store/checkout",
        json={"cart_token": token, "email": "ada@example.com", "shipping_address": SHIPPING},
        headers={"Idempotency-Key": "http-key-1"},
    )

    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "awaiting_payment"
    assert order["number"].startswith("NS-")
    assert order["lines"][0]["sku"] == "NEON-001"
    assert order["events"][0]["to_status"] == "awaiting_payment"

    fetched = await client.get(f"{BASE}/store/orders/{order['number']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == order["id"]


async def test_checkout_is_replay_safe_over_http(client, db_session):
    variant_id = await _published_variant_id(db_session)
    token = (await client.post(f"{BASE}/store/carts", json={})).json()["token"]
    await client.post(
        f"{BASE}/store/carts/{token}/lines",
        json={"variant_id": variant_id, "quantity": 1},
    )
    payload = {
        "cart_token": token,
        "email": "ada@example.com",
        "shipping_address": SHIPPING,
    }
    headers = {"Idempotency-Key": "http-replay"}

    first = await client.post(f"{BASE}/store/checkout", json=payload, headers=headers)
    second = await client.post(f"{BASE}/store/checkout", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_checkout_with_an_empty_cart_is_refused(client, db_session):
    await seed_world(db_session)
    token = (await client.post(f"{BASE}/store/carts", json={})).json()["token"]

    response = await client.post(
        f"{BASE}/store/checkout",
        json={"cart_token": token, "email": "ada@example.com", "shipping_address": SHIPPING},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CART_EMPTY"


async def test_health_and_readiness(client):
    health = await client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
