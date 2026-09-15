"""Test data builders shared across the suite."""

from __future__ import annotations

import uuid
from decimal import Decimal
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.admin.models import AdminUser
from app.domain.catalog.admin_service import CatalogAdminService
from app.domain.catalog.models import Product
from app.domain.catalog.schemas import ProductWrite
from app.domain.currency.models import Currency, ExchangeRate
from app.domain.i18n.models import Locale
from app.domain.inventory.service import InventoryService
from app.domain.region.models import Region, RegionLocale, RegionPaymentMethod

DEFAULT_RATES = {"CNY": Decimal("7.25"), "EUR": Decimal("0.92")}


async def seed_locales(session: AsyncSession) -> None:
    session.add_all(
        [
            Locale(code="zh-CN", name="简体中文", is_active=True, is_default=True, position=0),
            Locale(code="en", name="English", is_active=True, is_default=False, position=1),
        ]
    )
    await session.flush()


async def seed_currencies(session: AsyncSession) -> None:
    session.add_all(
        [
            Currency(code="USD", name="US Dollar", symbol="$", decimal_places=2),
            Currency(code="CNY", name="Chinese Yuan", symbol="¥", decimal_places=2),
            Currency(code="EUR", name="Euro", symbol="€", decimal_places=2),
            Currency(code="JPY", name="Japanese Yen", symbol="¥", decimal_places=0),
        ]
    )
    await session.flush()


async def seed_rates(
    session: AsyncSession, base: str = "USD", rates: dict[str, Decimal] | None = None
) -> None:
    for quote, rate in (rates or DEFAULT_RATES).items():
        session.add(
            ExchangeRate(base_code=base, quote_code=quote, rate=rate, source="test")
        )
    await session.flush()


async def seed_regions(session: AsyncSession) -> None:
    session.add_all(
        [
            Region(
                code="us",
                name="United States",
                currency_code="USD",
                tax_rate=Decimal("0.0700"),
                is_default=True,
                position=0,
            ),
            Region(
                code="cn",
                name="中国",
                currency_code="CNY",
                tax_rate=Decimal("0.0600"),
                is_default=False,
                position=1,
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            RegionLocale(region_code="us", locale="en"),
            RegionLocale(region_code="us", locale="zh-CN"),
            RegionLocale(region_code="cn", locale="zh-CN"),
            RegionPaymentMethod(region_code="us", provider_code="mock", is_active=True),
        ]
    )
    await session.flush()


async def seed_product(
    session: AsyncSession,
    name_en: str = "Neon Tee",
    name_zh: str = "霓虹 T 恤",
    slug: str = "neon-tee",
    sku: str = "NEON-001",
    base_price: Decimal = Decimal("19.99"),
    quantity: int = 10,
    status: str = "published",
    locales: list[str] | None = None,
) -> Product:
    catalog = CatalogAdminService(session)
    available_locales = locales or ["zh-CN", "en"]
    translations: dict[str, dict] = {}
    if "zh-CN" in available_locales:
        translations["zh-CN"] = {"name": name_zh, "slug": slug}
    if "en" in available_locales:
        translations["en"] = {"name": name_en, "slug": slug}

    product = await catalog.create_product(
        ProductWrite(
            status=status,
            base_price=base_price,
            base_currency="USD",
            translations=translations,
            variants=[{"sku": sku, "quantity": quantity}],
            media=[{"url": "https://cdn.example.com/neon.jpg", "alt": "Neon Tee"}],
        )
    )
    return product


async def seed_world(session: AsyncSession, **product_kwargs) -> Product:
    """Locales + currencies + rates + regions + one published product."""
    await seed_locales(session)
    await seed_currencies(session)
    await seed_rates(session)
    await seed_regions(session)
    return await seed_product(session, **product_kwargs)


async def set_variant_price(
    session: AsyncSession, variant_id: uuid.UUID, currency_code: str, amount: Decimal
) -> None:
    await CatalogAdminService(session).set_variant_price(variant_id, currency_code, amount)


ADMIN_EMAIL = "admin@neostore.test"
ADMIN_PASSWORD = "admin123"


@lru_cache(maxsize=8)
def _hash(password: str) -> str:
    """bcrypt is deliberately slow; hashing the same test password once is enough."""
    return hash_password(password)


async def seed_admin(
    session: AsyncSession,
    email: str = ADMIN_EMAIL,
    password: str = ADMIN_PASSWORD,
    role: str = "owner",
    is_active: bool = True,
) -> AdminUser:
    """An operator account. Authentication itself stays real, not stubbed."""
    user = AdminUser(
        email=email,
        password_hash=_hash(password),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()
    return user


__all__ = [
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "DEFAULT_RATES",
    "InventoryService",
    "seed_admin",
    "seed_currencies",
    "seed_locales",
    "seed_product",
    "seed_rates",
    "seed_regions",
    "seed_world",
    "set_variant_price",
]
