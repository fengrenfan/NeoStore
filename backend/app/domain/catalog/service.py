"""Catalog reads for both storefront and admin."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.domain_errors import NotFoundError
from app.domain.catalog.models import Media, Product, ProductStatus, ProductVariant
from app.domain.catalog.repository import CatalogRepository
from app.domain.currency.service import CurrencyService
from app.domain.i18n.service import I18nService
from app.domain.inventory.service import InventoryService
from app.domain.pricing.service import PricingService
from app.domain.region.models import Region


@dataclass(slots=True)
class VariantView:
    id: uuid.UUID
    sku: str
    label: str | None
    price: Decimal
    available: int


@dataclass(slots=True)
class MediaView:
    url: str
    alt: str | None


@dataclass(slots=True)
class ProductCard:
    id: uuid.UUID
    slug: str
    name: str
    price: Decimal
    currency: str
    status: str
    image: str | None = None


@dataclass(slots=True)
class ProductDetail:
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    seo_title: str | None
    seo_description: str | None
    price: Decimal
    currency: str
    status: str
    variants: list[VariantView] = field(default_factory=list)
    media: list[MediaView] = field(default_factory=list)


class CatalogService:
    def __init__(
        self,
        session: AsyncSession,
        pricing: PricingService | None = None,
        i18n: I18nService | None = None,
        inventory: InventoryService | None = None,
        currency: CurrencyService | None = None,
    ) -> None:
        self.session = session
        self._repo = CatalogRepository(session)
        self._pricing = pricing or PricingService(session)
        self._i18n = i18n or I18nService(session)
        self._inventory = inventory or InventoryService(session)
        self._currency = currency or CurrencyService(session)

    @staticmethod
    def _currency_for(region: Region | None, override: str | None) -> str:
        if override:
            return override.upper()
        if region is not None:
            return region.currency_code.upper()
        return settings.default_currency.upper()

    async def get_product_by_slug(
        self,
        slug: str,
        locale: str | None = None,
        region: Region | None = None,
        currency_code: str | None = None,
        include_unpublished: bool = False,
    ) -> ProductDetail:
        resolved_locale = await self._i18n.resolve_locale(locale)
        default_locale = await self._i18n.default_locale()

        product_id = await self._repo.find_product_id_by_slug(slug, resolved_locale)
        if product_id is None and resolved_locale != default_locale:
            product_id = await self._repo.find_product_id_by_slug(slug, default_locale)
        if product_id is None:
            raise NotFoundError(message="product not found", code="PRODUCT_NOT_FOUND")

        product = await self._repo.get(product_id)
        if product is None or (
            product.status != ProductStatus.PUBLISHED and not include_unpublished
        ):
            raise NotFoundError(message="product not found", code="PRODUCT_NOT_FOUND")

        return await self._to_detail(product, resolved_locale, region, currency_code)

    async def list_products(
        self,
        locale: str | None = None,
        region: Region | None = None,
        currency_code: str | None = None,
        category_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ProductCard], int]:
        resolved_locale = await self._i18n.resolve_locale(locale)
        target_currency = self._currency_for(region, currency_code)

        products = await self._repo.list_published(
            limit=limit, offset=offset, category_id=category_id
        )
        total = await self._repo.count_published(category_id=category_id)
        media = await self._repo.media_for("product", [p.id for p in products])

        cards: list[ProductCard] = []
        for product in products:
            translation = await self._i18n.translate(product.translations, resolved_locale)
            if translation is None:
                continue
            price = await self._representative_price(product, target_currency)
            images = media.get(product.id, [])
            cards.append(
                ProductCard(
                    id=product.id,
                    slug=translation.slug,
                    name=translation.name,
                    price=price,
                    currency=target_currency,
                    status=str(product.status),
                    image=images[0].url if images else None,
                )
            )
        return cards, total

    async def _representative_price(self, product: Product, currency: str) -> Decimal:
        """Cheapest variant price, falling back to the product base price."""
        if product.variants:
            prices = [await self._pricing.unit_price(v, currency) for v in product.variants]
            return min(prices)
        return await self._currency.convert(product.base_price, product.base_currency, currency)

    async def _to_detail(
        self,
        product: Product,
        locale: str,
        region: Region | None,
        currency_code: str | None,
    ) -> ProductDetail:
        target_currency = self._currency_for(region, currency_code)
        default_locale = await self._i18n.default_locale()
        translation = await self._i18n.translate(product.translations, locale)

        variants: list[VariantView] = []
        for variant in product.variants:
            price = await self._pricing.unit_price(variant, target_currency)
            variants.append(
                VariantView(
                    id=variant.id,
                    sku=variant.sku,
                    label=_label_for(variant, locale, default_locale),
                    price=price,
                    available=await self._inventory.available(variant.id),
                )
            )

        media = await self._repo.media_for("product", [product.id])
        images = [MediaView(url=row.url, alt=row.alt) for row in media.get(product.id, [])]

        cheapest = min((v.price for v in variants), default=None)
        if cheapest is None:
            cheapest = await self._currency.convert(
                product.base_price, product.base_currency, target_currency
            )

        return ProductDetail(
            id=product.id,
            slug=translation.slug if translation else "",
            name=translation.name if translation else "",
            description=translation.description if translation else None,
            seo_title=translation.seo_title if translation else None,
            seo_description=translation.seo_description if translation else None,
            price=cheapest,
            currency=target_currency,
            status=str(product.status),
            variants=variants,
            media=images,
        )


def _label_for(variant: ProductVariant, locale: str, default_locale: str) -> str | None:
    parts: list[str] = []
    for link in variant.option_values:
        value = link.option_value
        if value is None:
            continue
        row = next((t for t in value.translations if t.locale == locale), None)
        if row is None:
            row = next((t for t in value.translations if t.locale == default_locale), None)
        if row is not None:
            parts.append(row.label)
    return " / ".join(parts) if parts else None


__all__ = [
    "CatalogService",
    "MediaView",
    "ProductCard",
    "ProductDetail",
    "VariantView",
    "_label_for",
]

# Re-exported so callers do not need to reach into the models module.
__all__ += ["Media"]
