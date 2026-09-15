"""Idempotent bootstrap data.

Run after migrations::

    python -m app.seed                 # seed what is missing, refresh FX rates
    python -m app.seed --create-all    # also create the schema (fresh SQLite dev)
    python -m app.seed --skip-rates    # never touch the network

Every step looks up its own natural key first, so running this twice is safe and
the second run reports everything as already present. Nothing here deletes or
overwrites catalog content.

Deliberately *not* idempotent-by-overwrite: a product that already exists is left
exactly as the operator left it. Seed data is a starting point, not a source of
truth that keeps re-asserting itself.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domain
from app.core.config import settings
from app.core.domain_errors import ExchangeRateUnavailableError
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import async_session_factory, dispose_engine, engine
from app.domain.admin.models import AdminUser
from app.domain.catalog.admin_service import CatalogAdminService
from app.domain.catalog.models import (
    Category,
    ProductCategory,
)
from app.domain.catalog.repository import CatalogRepository
from app.domain.catalog.schemas import ProductWrite
from app.domain.currency.models import Currency
from app.domain.currency.repository import CurrencyRepository
from app.domain.currency.service import CurrencyService
from app.domain.i18n.models import Locale
from app.domain.region.models import Region, RegionLocale, RegionPaymentMethod
from app.integrations.exchange_rate import ExchangeRateProvider

logger = logging.getLogger("neostore.seed")

BASE_CURRENCY = settings.default_currency.upper()
DEFAULT_LOCALE = settings.default_locale

#: Last-resort rates so a fresh, offline install still prices correctly. The
#: worker replaces these with live values as soon as the provider is reachable.
FALLBACK_RATES: dict[str, Decimal] = {
    "CNY": Decimal("7.25"),
    "EUR": Decimal("0.92"),
    "GBP": Decimal("0.79"),
    "JPY": Decimal("151.00"),
}

LOCALES: tuple[dict, ...] = (
    {"code": "zh-CN", "name": "简体中文", "is_default": True, "position": 0},
    {"code": "en", "name": "English", "is_default": False, "position": 1},
    {"code": "ja", "name": "日本語", "is_default": False, "position": 2},
)

CURRENCIES: tuple[dict, ...] = (
    {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥", "decimal_places": 2},
    {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_places": 2},
    {"code": "GBP", "name": "Pound Sterling", "symbol": "£", "decimal_places": 2},
    # Zero-decimal currency: the rounding path that catches naive *100 maths.
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimal_places": 0},
)

#: A region binds exactly one currency, a tax rate and its accepted locales.
REGIONS: tuple[dict, ...] = (
    {
        "code": "us",
        "name": "United States",
        "currency_code": "USD",
        "tax_rate": Decimal("0.0700"),
        "is_default": True,
        "position": 0,
        "locales": ["en", "zh-CN"],
        "payment_methods": ["mock"],
    },
    {
        "code": "cn",
        "name": "中国",
        "currency_code": "CNY",
        "tax_rate": Decimal("0.0600"),
        "is_default": False,
        "position": 1,
        "locales": ["zh-CN", "en"],
        "payment_methods": ["mock"],
    },
    {
        "code": "eu",
        "name": "European Union",
        "currency_code": "EUR",
        "tax_rate": Decimal("0.2100"),
        "is_default": False,
        "position": 2,
        "locales": ["en"],
        "payment_methods": ["mock"],
    },
    {
        "code": "jp",
        "name": "日本",
        "currency_code": "JPY",
        "tax_rate": Decimal("0.1000"),
        "is_default": False,
        "position": 3,
        "locales": ["ja", "en"],
        "payment_methods": ["mock"],
    },
)

CATEGORIES: tuple[dict, ...] = (
    {
        "key": "apparel",
        "translations": {
            "zh-CN": {"name": "服饰", "slug": "apparel"},
            "en": {"name": "Apparel", "slug": "apparel"},
            "ja": {"name": "アパレル", "slug": "apparel"},
        },
    },
    {
        "key": "footwear",
        "translations": {
            "zh-CN": {"name": "鞋履", "slug": "footwear"},
            "en": {"name": "Footwear", "slug": "footwear"},
            "ja": {"name": "フットウェア", "slug": "footwear"},
        },
    },
)

#: Products only carry zh-CN and en text on purpose — the `ja` region exercises
#: the fallback chain (requested locale -> default locale) rather than a third
#: copy of the same strings.
PRODUCTS: tuple[dict, ...] = (
    {
        "slug": "neon-tee",
        "category": "apparel",
        "status": "published",
        "base_price": Decimal("19.99"),
        "position": 0,
        "translations": {
            "zh-CN": {
                "name": "霓虹 T 恤",
                "slug": "neon-tee",
                "description": "重磅纯棉，落肩剪裁，胸前渐变霓虹印花。",
                "seo_title": "霓虹 T 恤",
                "seo_description": "重磅纯棉霓虹 T 恤，全球直邮。",
            },
            "en": {
                "name": "Neon Tee",
                "slug": "neon-tee",
                "description": "Heavyweight cotton, dropped shoulders, gradient neon print.",
                "seo_title": "Neon Tee",
                "seo_description": "Heavyweight cotton neon tee, shipped worldwide.",
            },
        },
        "variants": [
            {
                "sku": "NEON-TEE-S",
                "quantity": 40,
                # Explicit price wins over base_price x rate; this variant shows
                # the operator-set path while its sibling shows the converted one.
                "prices": {"CNY": Decimal("149.00")},
            },
            {"sku": "NEON-TEE-M", "quantity": 35},
        ],
        "media": [
            {
                "url": "https://cdn.neostore.local/products/neon-tee-front.jpg",
                "alt": "Neon Tee, front",
                "is_primary": True,
            },
            {
                "url": "https://cdn.neostore.local/products/neon-tee-detail.jpg",
                "alt": "Neon Tee, print detail",
                "is_primary": False,
            },
        ],
    },
    {
        "slug": "aurora-hoodie",
        "category": "apparel",
        "status": "published",
        "base_price": Decimal("68.00"),
        "position": 1,
        "translations": {
            "zh-CN": {
                "name": "极光卫衣",
                "slug": "aurora-hoodie",
                "description": "双面绒内里，极光渐变刺绣，秋冬保暖首选。",
                "seo_title": "极光卫衣",
                "seo_description": "极光渐变刺绣连帽卫衣，全球直邮。",
            },
            "en": {
                "name": "Aurora Hoodie",
                "slug": "aurora-hoodie",
                "description": "Brushed fleece lining with aurora gradient embroidery.",
                "seo_title": "Aurora Hoodie",
                "seo_description": "Aurora gradient embroidered hoodie, shipped worldwide.",
            },
        },
        "variants": [
            {"sku": "AURORA-HOODIE-S", "quantity": 25},
            {"sku": "AURORA-HOODIE-L", "quantity": 18},
        ],
        "media": [
            {
                "url": "https://cdn.neostore.local/products/aurora-hoodie.jpg",
                "alt": "Aurora Hoodie",
                "is_primary": True,
            }
        ],
    },
    {
        "slug": "pulse-sneakers",
        "category": "footwear",
        "status": "published",
        "base_price": Decimal("129.00"),
        "position": 2,
        "translations": {
            "zh-CN": {
                "name": "脉冲运动鞋",
                "slug": "pulse-sneakers",
                "description": "回弹中底与夜光侧条，长时间行走不累脚。",
                "seo_title": "脉冲运动鞋",
                "seo_description": "夜光侧条回弹运动鞋，全球直邮。",
            },
            "en": {
                "name": "Pulse Sneakers",
                "slug": "pulse-sneakers",
                "description": "Responsive midsole with glow-in-the-dark side stripes.",
                "seo_title": "Pulse Sneakers",
                "seo_description": "Glow-striped responsive sneakers, shipped worldwide.",
            },
        },
        "variants": [
            {"sku": "PULSE-SNKR-41", "quantity": 12, "prices": {"CNY": Decimal("929.00")}},
            {"sku": "PULSE-SNKR-43", "quantity": 9},
        ],
        "media": [
            {
                "url": "https://cdn.neostore.local/products/pulse-sneakers.jpg",
                "alt": "Pulse Sneakers",
                "is_primary": True,
            }
        ],
    },
)


@dataclass
class SeedReport:
    """What actually changed, so the CLI can say something useful."""

    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def created_(self, label: str) -> None:
        self.created.append(label)

    def skipped_(self, label: str) -> None:
        self.skipped.append(label)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def render(self) -> str:
        lines = [f"created: {len(self.created)}", f"already present: {len(self.skipped)}"]
        lines += [f"  + {item}" for item in self.created]
        lines += [f"  = {item}" for item in self.skipped]
        lines += [f"  ! {item}" for item in self.notes]
        return "\n".join(lines)


async def seed_locales(session: AsyncSession, report: SeedReport) -> None:
    for spec in LOCALES:
        if await session.get(Locale, spec["code"]) is not None:
            report.skipped_(f"locale {spec['code']}")
            continue
        session.add(Locale(**spec))
        report.created_(f"locale {spec['code']}")
    await session.flush()


async def seed_currencies(session: AsyncSession, report: SeedReport) -> None:
    repo = CurrencyRepository(session)
    for spec in CURRENCIES:
        if await repo.get(spec["code"]) is not None:
            report.skipped_(f"currency {spec['code']}")
            continue
        await repo.upsert_currency(Currency(**spec, is_active=True))
        report.created_(f"currency {spec['code']}")


async def seed_regions(session: AsyncSession, report: SeedReport) -> None:
    for spec in REGIONS:
        locales = spec["locales"]
        methods = spec["payment_methods"]
        if await session.get(Region, spec["code"]) is not None:
            report.skipped_(f"region {spec['code']}")
            continue
        session.add(
            Region(
                code=spec["code"],
                name=spec["name"],
                currency_code=spec["currency_code"],
                tax_rate=spec["tax_rate"],
                is_default=spec["is_default"],
                position=spec["position"],
                locale_links=[RegionLocale(locale=code) for code in locales],
                payment_method_links=[
                    RegionPaymentMethod(provider_code=code, is_active=True)
                    for code in methods
                ],
            )
        )
        report.created_(f"region {spec['code']} -> {spec['currency_code']}")
    await session.flush()


async def seed_admin(
    session: AsyncSession,
    report: SeedReport,
    *,
    reset_password: bool = False,
) -> None:
    email = settings.seed_admin_email
    stmt = select(AdminUser).where(AdminUser.email == email)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        session.add(
            AdminUser(
                email=email,
                password_hash=hash_password(settings.seed_admin_password),
                role="owner",
                is_active=True,
            )
        )
        await session.flush()
        report.created_(f"admin {email}")
        return

    if reset_password:
        user.password_hash = hash_password(settings.seed_admin_password)
        await session.flush()
        report.created_(f"admin {email} password reset")
        return

    report.skipped_(f"admin {email}")


async def seed_categories(session: AsyncSession, report: SeedReport) -> dict[str, Category]:
    catalog = CatalogAdminService(session)
    by_key: dict[str, Category] = {}

    for spec in CATEGORIES:
        slug = next(iter(spec["translations"].values()))["slug"]
        existing = await CatalogRepository(session).category_by_slug(slug, DEFAULT_LOCALE)
        if existing is None:
            # Fall back across locales: a category may exist with only en text.
            for locale in ("en", "ja"):
                existing = await CatalogRepository(session).category_by_slug(slug, locale)
                if existing is not None:
                    break
        if existing is not None:
            by_key[spec["key"]] = existing
            report.skipped_(f"category {spec['key']}")
            continue
        by_key[spec["key"]] = await catalog.create_category(spec["translations"])
        report.created_(f"category {spec['key']}")

    return by_key


async def seed_products(
    session: AsyncSession,
    report: SeedReport,
    categories: dict[str, Category],
) -> None:
    catalog = CatalogAdminService(session)
    repo = CatalogRepository(session)

    for spec in PRODUCTS:
        slug = spec["slug"]
        if await repo.find_product_id_by_slug(slug, DEFAULT_LOCALE) is not None:
            report.skipped_(f"product {slug}")
            continue

        product = await catalog.create_product(
            ProductWrite(
                status=spec["status"],
                base_price=spec["base_price"],
                base_currency=BASE_CURRENCY,
                position=spec["position"],
                translations=spec["translations"],
                variants=[
                    {
                        "sku": variant["sku"],
                        "quantity": variant["quantity"],
                        "prices": variant.get("prices", {}),
                    }
                    for variant in spec["variants"]
                ],
                media=[
                    {
                        "url": media["url"],
                        "alt": media.get("alt"),
                        "is_primary": media.get("is_primary", False),
                    }
                    for media in spec["media"]
                ],
            )
        )

        category = categories.get(spec["category"])
        if category is not None:
            session.add(
                ProductCategory(product_id=product.id, category_id=category.id)
            )
        report.created_(f"product {slug}")

    await session.flush()


async def seed_exchange_rates(
    session: AsyncSession,
    report: SeedReport,
    *,
    provider: ExchangeRateProvider | None = None,
    refresh: bool = True,
) -> None:
    """Live rates when possible, baked-in fallbacks when offline."""
    repo = CurrencyRepository(session)
    tracked = {spec["code"] for spec in CURRENCIES} - {BASE_CURRENCY}

    if refresh:
        try:
            updated = await CurrencyService(session, provider=provider).refresh_rates(
                BASE_CURRENCY
            )
            report.created_(f"{updated} live exchange rates from the provider")
            return
        except ExchangeRateUnavailableError as exc:
            report.note(
                f"rate provider unavailable ({exc.message}); using fallback rates"
            )

    written = 0
    for quote, rate in FALLBACK_RATES.items():
        if quote not in tracked:
            continue
        existing = await repo.get_rate(BASE_CURRENCY, quote)
        if existing is not None and not refresh:
            continue
        await repo.upsert_rate(BASE_CURRENCY, quote, rate, "seed-fallback")
        written += 1

    if written:
        report.created_(f"{written} fallback exchange rates")
    else:
        report.skipped_("exchange rates")


async def run_seed(
    session: AsyncSession,
    *,
    provider: ExchangeRateProvider | None = None,
    refresh_rates: bool = True,
    reset_admin_password: bool = False,
) -> SeedReport:
    """Bring an empty database up to a usable demo state. Safe to re-run."""
    report = SeedReport()

    # Reference data first: regions reference currencies, translations reference locales.
    await seed_locales(session, report)
    await seed_currencies(session, report)
    await seed_regions(session, report)
    await seed_admin(session, report, reset_password=reset_admin_password)
    await seed_exchange_rates(
        session, report, provider=provider, refresh=refresh_rates
    )
    categories = await seed_categories(session, report)
    await seed_products(session, report, categories)

    await session.commit()
    return report


async def _counts(session: AsyncSession) -> dict[str, int]:
    from app.domain.catalog.models import Product

    return {
        "locales": int(
            (await session.execute(select(func.count()).select_from(Locale))).scalar_one()
        ),
        "currencies": int(
            (await session.execute(select(func.count()).select_from(Currency))).scalar_one()
        ),
        "regions": int(
            (await session.execute(select(func.count()).select_from(Region))).scalar_one()
        ),
        "products": int(
            (await session.execute(select(func.count()).select_from(Product))).scalar_one()
        ),
    }


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed NeoStore with demo data")
    parser.add_argument(
        "--create-all",
        action="store_true",
        help="create the schema first (convenient on a fresh SQLite file)",
    )
    parser.add_argument(
        "--skip-rates",
        action="store_true",
        help="do not call the exchange-rate provider",
    )
    parser.add_argument(
        "--reset-admin-password",
        action="store_true",
        help="overwrite the seeded admin password with SEED_ADMIN_PASSWORD",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    app.domain.load_models()
    if args.create_all:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("schema ensured via create_all")

    try:
        async with async_session_factory() as session:
            report = await run_seed(
                session,
                refresh_rates=not args.skip_rates,
                reset_admin_password=args.reset_admin_password,
            )
            counts = await _counts(session)
    finally:
        await dispose_engine()

    print(report.render())
    print("totals: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    print(f"admin login: {settings.seed_admin_email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
