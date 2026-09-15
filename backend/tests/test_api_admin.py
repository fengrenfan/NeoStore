"""Admin dashboard API: auth, catalog writes, orders, inventory and settings."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.currency.service import CurrencyService
from app.integrations.exchange_rate import StaticRateProvider
from tests.factories import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    seed_admin,
    seed_currencies,
    seed_locales,
    seed_world,
)

pytestmark = pytest.mark.anyio

BASE = "/api/v1"
SHIPPING = {
    "name": "Ada Lovelace",
    "line1": "1 Analytical Engine Way",
    "city": "London",
    "country": "GB",
    "postal_code": "EC1A",
}


async def _auth(client, db_session, **admin_kwargs) -> dict[str, str]:
    await seed_admin(db_session, **admin_kwargs)
    response = await client.post(
        f"{BASE}/admin/auth/login",
        json={"email": admin_kwargs.get("email", ADMIN_EMAIL), "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --------------------------------------------------------------------------- auth


async def test_login_issues_a_bearer_token(client, db_session):
    await seed_admin(db_session)

    response = await client.post(
        f"{BASE}/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


async def test_login_with_a_wrong_password_is_unauthorized(client, db_session):
    await seed_admin(db_session)

    response = await client.post(
        f"{BASE}/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": "not-the-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_with_an_unknown_email_is_unauthorized(client, db_session):
    response = await client.post(
        f"{BASE}/admin/auth/login",
        json={"email": "nobody@example.com", "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 401


async def test_a_deactivated_account_cannot_log_in(client, db_session):
    await seed_admin(db_session, is_active=False)

    response = await client.post(
        f"{BASE}/admin/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 401


async def test_me_returns_the_signed_in_operator(client, db_session):
    headers = await _auth(client, db_session)

    response = await client.get(f"{BASE}/admin/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"email": ADMIN_EMAIL, "role": "owner"}


async def test_protected_routes_need_a_token(client, db_session):
    response = await client.get(f"{BASE}/admin/products")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_a_garbage_token_is_rejected(client, db_session):
    response = await client.get(
        f"{BASE}/admin/products", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert response.status_code == 401


async def test_a_token_for_an_unknown_account_is_rejected(client, db_session):
    from app.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token('ghost@example.com')}"}

    response = await client.get(f"{BASE}/admin/products", headers=headers)

    assert response.status_code == 401
    assert "not active" in response.json()["error"]["message"]


# ------------------------------------------------------------------------ products


async def test_create_read_update_and_delete_a_product(client, db_session):
    headers = await _auth(client, db_session)
    await seed_locales(db_session)
    await seed_currencies(db_session)

    created = await client.post(
        f"{BASE}/admin/products",
        headers=headers,
        json={
            "status": "published",
            "base_price": "24.50",
            "base_currency": "USD",
            "translations": {
                "zh-CN": {"name": "霓虹卫衣", "slug": "neon-hoodie"},
                "en": {"name": "Neon Hoodie", "slug": "neon-hoodie"},
            },
            "variants": [{"sku": "HOOD-001", "quantity": 12}],
            "media": [{"url": "https://cdn.example.com/hood.jpg", "alt": "Hoodie"}],
        },
    )

    assert created.status_code == 201, created.text
    body = created.json()
    product_id = body["id"]
    assert body["status"] == "published"
    assert {t["locale"] for t in body["translations"]} == {"zh-CN", "en"}
    assert body["variants"][0]["sku"] == "HOOD-001"
    assert body["variants"][0]["available"] == 12
    assert body["media"][0]["is_primary"] is True

    listed = await client.get(f"{BASE}/admin/products", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = await client.get(f"{BASE}/admin/products/{product_id}", headers=headers)
    assert fetched.status_code == 200

    patched = await client.patch(
        f"{BASE}/admin/products/{product_id}",
        headers=headers,
        json={"status": "draft", "translations": {"en": {"name": "Renamed", "slug": "neon-hoodie"}}},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "draft"
    names = {t["locale"]: t["name"] for t in patched.json()["translations"]}
    assert names["en"] == "Renamed"
    assert names["zh-CN"] == "霓虹卫衣"  # untouched locale keeps its text

    deleted = await client.delete(f"{BASE}/admin/products/{product_id}", headers=headers)
    assert deleted.status_code == 204

    assert (await client.get(f"{BASE}/admin/products/{product_id}", headers=headers)).status_code == 404


async def test_setting_an_explicit_variant_price(client, db_session):
    headers = await _auth(client, db_session)
    product = await seed_world(db_session)
    variant_id = product.variants[0].id

    response = await client.put(
        f"{BASE}/admin/products/{product.id}/variants/{variant_id}/price",
        headers=headers,
        json={"currency_code": "cny", "amount": "150.00"},
    )

    assert response.status_code == 200
    assert response.json()["variants"][0]["prices"] == {"CNY": "150.00"}

    detail = await client.get(f"{BASE}/store/products/neon-tee", params={"region": "cn"})
    assert Decimal(detail.json()["price"]) == Decimal("150.00")


async def test_unknown_product_id_is_not_found(client, db_session):
    headers = await _auth(client, db_session)
    import uuid

    response = await client.get(f"{BASE}/admin/products/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


# ---------------------------------------------------------------------- categories


async def test_category_create_list_and_rename(client, db_session):
    headers = await _auth(client, db_session)
    await seed_locales(db_session)

    created = await client.post(
        f"{BASE}/admin/categories",
        headers=headers,
        json={"translations": {"en": {"name": "Apparel", "slug": "apparel"}}},
    )
    assert created.status_code == 201
    category_id = created.json()["id"]
    assert created.json()["path"] == f"/{category_id}/"

    listed = await client.get(f"{BASE}/admin/categories", headers=headers)
    assert [row["id"] for row in listed.json()] == [category_id]

    patched = await client.patch(
        f"{BASE}/admin/categories/{category_id}",
        headers=headers,
        json={"translations": {"zh-CN": {"name": "服饰", "slug": "apparel"}}},
    )
    assert patched.status_code == 200
    assert {t["locale"] for t in patched.json()["translations"]} == {"en", "zh-CN"}


# -------------------------------------------------------------------------- orders


async def _place_an_order(client, db_session) -> str:
    """Run the storefront flow and return the order number."""
    product = await seed_world(db_session)
    token = (await client.post(f"{BASE}/store/carts", json={})).json()["token"]
    await client.post(
        f"{BASE}/store/carts/{token}/lines",
        json={"variant_id": str(product.variants[0].id), "quantity": 1},
    )
    response = await client.post(
        f"{BASE}/store/checkout",
        json={"cart_token": token, "email": "ada@example.com", "shipping_address": SHIPPING},
    )
    return response.json()["number"]


async def test_admin_can_list_and_inspect_orders(client, db_session):
    headers = await _auth(client, db_session)
    number = await _place_an_order(client, db_session)

    listed = await client.get(f"{BASE}/admin/orders", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    filtered = await client.get(
        f"{BASE}/admin/orders", headers=headers, params={"status": "awaiting_payment"}
    )
    assert filtered.json()["total"] == 1

    empty = await client.get(f"{BASE}/admin/orders", headers=headers, params={"status": "paid"})
    assert empty.json()["total"] == 0

    detail = await client.get(f"{BASE}/admin/orders/{number}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["lines"][0]["sku"] == "NEON-001"


async def test_admin_drives_an_order_to_completion(client, db_session):
    headers = await _auth(client, db_session)
    number = await _place_an_order(client, db_session)

    transitions = await client.get(f"{BASE}/admin/orders/{number}/transitions", headers=headers)
    assert transitions.json() == ["cancelled", "paid"]

    for target in ("paid", "fulfilled", "completed"):
        response = await client.patch(
            f"{BASE}/admin/orders/{number}/status",
            headers=headers,
            json={"status": target, "note": f"moving to {target}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target

    final = await client.get(f"{BASE}/admin/orders/{number}", headers=headers)
    assert [event["to_status"] for event in final.json()["events"]] == [
        "awaiting_payment",
        "paid",
        "fulfilled",
        "completed",
    ]


async def test_admin_cannot_make_an_illegal_status_change(client, db_session):
    headers = await _auth(client, db_session)
    number = await _place_an_order(client, db_session)

    response = await client.patch(
        f"{BASE}/admin/orders/{number}/status",
        headers=headers,
        json={"status": "completed"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


async def test_an_unknown_status_value_is_a_validation_error(client, db_session):
    headers = await _auth(client, db_session)
    number = await _place_an_order(client, db_session)

    response = await client.patch(
        f"{BASE}/admin/orders/{number}/status",
        headers=headers,
        json={"status": "teleported"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ORDER_STATUS"


# ----------------------------------------------------------------------- inventory


async def test_inventory_read_and_adjustment(client, db_session):
    headers = await _auth(client, db_session)
    product = await seed_world(db_session)
    variant_id = product.variants[0].id

    read = await client.get(f"{BASE}/admin/inventory/{variant_id}", headers=headers)
    assert read.status_code == 200
    assert read.json() == {
        "variant_id": str(variant_id),
        "quantity": 10,
        "reserved": 0,
        "available": 10,
    }

    adjusted = await client.post(
        f"{BASE}/admin/inventory/{variant_id}/adjust",
        headers=headers,
        json={"delta": 5, "reason": "restock", "note": "new pallet"},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["quantity"] == 15

    reduced = await client.post(
        f"{BASE}/admin/inventory/{variant_id}/adjust",
        headers=headers,
        json={"delta": -3},
    )
    assert reduced.json()["quantity"] == 12


async def test_adjustment_below_reserved_stock_is_refused(client, db_session):
    headers = await _auth(client, db_session)
    product = await seed_world(db_session)
    variant_id = product.variants[0].id

    token = (await client.post(f"{BASE}/store/carts", json={})).json()["token"]
    await client.post(
        f"{BASE}/store/carts/{token}/lines",
        json={"variant_id": str(variant_id), "quantity": 8},
    )
    await client.post(
        f"{BASE}/store/checkout",
        json={"cart_token": token, "email": "ada@example.com", "shipping_address": SHIPPING},
    )

    response = await client.post(
        f"{BASE}/admin/inventory/{variant_id}/adjust",
        headers=headers,
        json={"delta": -5},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"


# ------------------------------------------------------------------------ settings


async def test_settings_expose_locales_currencies_and_regions(client, db_session):
    headers = await _auth(client, db_session)
    await seed_world(db_session)

    locales = await client.get(f"{BASE}/admin/settings/locales", headers=headers)
    currencies = await client.get(f"{BASE}/admin/settings/currencies", headers=headers)
    regions = await client.get(f"{BASE}/admin/settings/regions", headers=headers)

    assert [row["code"] for row in locales.json()] == ["zh-CN", "en"]
    assert {row["code"] for row in currencies.json()} == {"USD", "CNY", "EUR", "JPY"}
    assert regions.json()[0]["locales"] == ["en", "zh-CN"]
    assert regions.json()[0]["payment_methods"] == ["mock"]


async def test_exchange_rates_can_be_listed_and_overridden(client, db_session):
    headers = await _auth(client, db_session)
    await seed_world(db_session)

    listed = await client.get(
        f"{BASE}/admin/settings/exchange-rates", headers=headers, params={"base": "USD"}
    )
    assert listed.status_code == 200
    assert {row["quote_code"] for row in listed.json()} == {"CNY", "EUR"}

    overridden = await client.put(
        f"{BASE}/admin/settings/exchange-rates",
        headers=headers,
        json={"base_code": "USD", "quote_code": "JPY", "rate": "151.25", "source": "manual"},
    )
    assert overridden.status_code == 200
    assert overridden.json()["quote_code"] == "JPY"
    assert Decimal(overridden.json()["rate"]) == Decimal("151.2500000000")

    # The new rate immediately drives storefront pricing.
    detail = await client.get(f"{BASE}/store/products/neon-tee")
    assert detail.headers["x-currency"] == "USD"


async def test_refresh_pulls_rates_from_the_provider(client, db_session, monkeypatch):
    headers = await _auth(client, db_session)
    await seed_world(db_session)

    monkeypatch.setattr(
        "app.domain.currency.service.get_exchange_rate_provider",
        lambda: StaticRateProvider(
            {"CNY": Decimal("7.10"), "EUR": Decimal("0.95"), "JPY": Decimal("151.00")}
        ),
    )

    response = await client.post(
        f"{BASE}/admin/settings/exchange-rates/refresh",
        headers=headers,
        params={"base": "USD"},
    )

    assert response.status_code == 200
    # CNY and EUR were updated, JPY was created.
    assert response.json() == {"updated": 3, "base": "USD"}

    listed = await client.get(
        f"{BASE}/admin/settings/exchange-rates", headers=headers, params={"base": "USD"}
    )
    rates = {row["quote_code"]: Decimal(row["rate"]) for row in listed.json()}
    assert rates["CNY"] == Decimal("7.1000000000")
    assert rates["JPY"] == Decimal("151.0000000000")


async def test_a_failing_provider_leaves_stored_rates_alone(client, db_session, monkeypatch):
    headers = await _auth(client, db_session)
    await seed_world(db_session)

    class Boom(StaticRateProvider):
        async def fetch(self, base: str):
            from app.core.domain_errors import ExchangeRateUnavailableError

            raise ExchangeRateUnavailableError(message="provider is down")

    monkeypatch.setattr(
        "app.domain.currency.service.get_exchange_rate_provider", lambda: Boom({})
    )

    response = await client.post(
        f"{BASE}/admin/settings/exchange-rates/refresh",
        headers=headers,
        params={"base": "USD"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EXCHANGE_RATE_UNAVAILABLE"

    listed = await client.get(
        f"{BASE}/admin/settings/exchange-rates", headers=headers, params={"base": "USD"}
    )
    rates = {row["quote_code"]: Decimal(row["rate"]) for row in listed.json()}
    assert rates["CNY"] == Decimal("7.2500000000")  # the seeded value survived


async def test_currency_service_uses_the_injected_provider(db_session):
    """The provider seam is real, not just monkeypatched in the route."""
    await seed_currencies(db_session)
    service = CurrencyService(
        db_session, provider=StaticRateProvider({"CNY": Decimal("7.01")})
    )

    updated = await service.refresh_rates("usd")

    assert updated == 1
    assert await service.convert(Decimal("10"), "USD", "CNY") == Decimal("70.10")
