"""Write-side catalog operations used by the admin dashboard."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError
from app.domain.catalog.models import (
    Category,
    CategoryTranslation,
    Media,
    Product,
    ProductStatus,
    ProductTranslation,
    ProductVariant,
    VariantPrice,
)
from app.domain.catalog.repository import CatalogRepository
from app.domain.catalog.schemas import (
    AdminMediaRead,
    AdminProductRead,
    AdminTranslationRead,
    AdminVariantRead,
)
from app.domain.inventory.service import InventoryService


class CatalogAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = CatalogRepository(session)
        self._inventory = InventoryService(session)

    async def to_admin_read(self, product: Product) -> AdminProductRead:
        media = await self._repo.media_for("product", [product.id])
        variants: list[AdminVariantRead] = []
        for variant in product.variants:
            variants.append(
                AdminVariantRead(
                    id=variant.id,
                    sku=variant.sku,
                    position=variant.position,
                    prices={row.currency_code: row.amount for row in variant.prices},
                    available=await self._inventory.available(variant.id),
                )
            )
        return AdminProductRead(
            id=product.id,
            status=str(product.status),
            product_type=product.product_type,
            base_price=product.base_price,
            base_currency=product.base_currency,
            position=product.position,
            translations=[
                AdminTranslationRead.model_validate(row) for row in product.translations
            ],
            variants=variants,
            media=[AdminMediaRead.model_validate(row) for row in media.get(product.id, [])],
        )

    async def count_products(self) -> int:
        return int(
            (await self.session.execute(select(func.count()).select_from(Product))).scalar_one()
        )

    async def list_products(self, limit: int = 50, offset: int = 0) -> tuple[list[Product], int]:
        products = await self._repo.list_all(limit=limit, offset=offset)
        return products, await self.count_products()

    async def get_product(self, product_id: uuid.UUID) -> Product:
        product = await self._repo.get(product_id)
        if product is None:
            raise NotFoundError(message="product not found", code="PRODUCT_NOT_FOUND")
        return product

    async def create_product(self, payload: Any) -> Product:
        product = Product(
            status=self._status(payload.status),
            product_type=payload.product_type,
            base_price=Decimal(str(payload.base_price)),
            base_currency=str(payload.base_currency).upper(),
            position=payload.position,
            # Collections are initialised explicitly: a brand new instance has
            # them unloaded (``NO_VALUE``), and the first access would trigger a
            # lazy load that async SQLAlchemy cannot service.
            translations=[],
            variants=[],
        )
        self.session.add(product)
        await self.session.flush()

        await self._apply_translations(product, payload.translations or {})

        variants = payload.variants or []
        if not variants:
            variants = [{"sku": f"{product.id.hex[:8]}-1", "quantity": 0}]
        for index, spec in enumerate(variants):
            await self.add_variant(
                product,
                sku=spec.get("sku") or f"{product.id.hex[:8]}-{index + 1}",
                prices=spec.get("prices") or {},
                quantity=int(spec.get("quantity", 0)),
                position=index,
            )

        for index, spec in enumerate(payload.media or []):
            self.session.add(
                Media(
                    owner_type="product",
                    owner_id=product.id,
                    url=spec["url"],
                    alt=spec.get("alt"),
                    position=int(spec.get("position", index)),
                    is_primary=bool(spec.get("is_primary", index == 0)),
                )
            )

        await self.session.flush()
        return product

    async def update_product(self, product_id: uuid.UUID, payload: Any) -> Product:
        product = await self.get_product(product_id)
        if payload.status is not None:
            product.status = self._status(payload.status)
        if payload.base_price is not None:
            product.base_price = Decimal(str(payload.base_price))
        if payload.base_currency is not None:
            product.base_currency = str(payload.base_currency).upper()
        if payload.position is not None:
            product.position = payload.position
        if payload.translations is not None:
            await self._apply_translations(product, payload.translations)
        await self.session.flush()
        return product

    async def delete_product(self, product_id: uuid.UUID) -> None:
        product = await self.get_product(product_id)
        await self.session.delete(product)
        await self.session.flush()

    async def add_variant(
        self,
        product: Product,
        sku: str,
        prices: dict[str, Any],
        quantity: int,
        position: int = 0,
    ) -> ProductVariant:
        variant = ProductVariant(
            product_id=product.id, sku=sku, position=position, prices=[], option_values=[]
        )
        # Append through the parent so ``product.variants`` stays in sync with
        # what was just written, instead of requiring a re-query.
        product.variants.append(variant)
        await self.session.flush()

        for code, amount in prices.items():
            variant.prices.append(
                VariantPrice(
                    currency_code=str(code).upper(),
                    amount=Decimal(str(amount)),
                )
            )

        await self._inventory.ensure_item(variant.id, quantity=quantity)
        await self.session.flush()
        return variant

    async def set_variant_price(
        self, variant_id: uuid.UUID, currency_code: str, amount: Decimal
    ) -> VariantPrice:
        code = currency_code.upper()
        stmt = select(VariantPrice).where(
            VariantPrice.variant_id == variant_id, VariantPrice.currency_code == code
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            variant = await self.session.get(ProductVariant, variant_id)
            if variant is None:
                raise NotFoundError(message="variant not found", code="VARIANT_NOT_FOUND")
            row = VariantPrice(variant_id=variant_id, currency_code=code, amount=amount)
            # Append through the variant so an aggregate read straight back out
            # of this session already reports the new price.
            variant.prices.append(row)
        else:
            row.amount = amount
        await self.session.flush()
        return row

    async def list_categories(self) -> list[Category]:
        return await self._repo.list_categories()

    async def create_category(
        self, translations: dict[str, dict], parent_id: uuid.UUID | None = None
    ) -> Category:
        category = Category(parent_id=parent_id, path="/", translations=[])
        self.session.add(category)
        await self.session.flush()
        category.path = f"/{category.id}/" if parent_id is None else f"/{parent_id}/{category.id}/"
        for locale, fields in translations.items():
            category.translations.append(
                CategoryTranslation(
                    category_id=category.id,
                    locale=locale,
                    name=fields.get("name", ""),
                    slug=fields.get("slug", ""),
                    description=fields.get("description"),
                    seo_title=fields.get("seo_title"),
                    seo_description=fields.get("seo_description"),
                )
            )
        await self.session.flush()
        return category

    async def upsert_category_translations(
        self, category_id: uuid.UUID, translations: dict[str, dict]
    ) -> Category:
        category = await self._repo.get_category(category_id)
        if category is None:
            raise NotFoundError(message="category not found", code="CATEGORY_NOT_FOUND")
        for locale, fields in translations.items():
            existing = next((t for t in category.translations if t.locale == locale), None)
            if existing is None:
                category.translations.append(
                    CategoryTranslation(
                        category_id=category.id,
                        locale=locale,
                        name=fields.get("name", ""),
                        slug=fields.get("slug", ""),
                        description=fields.get("description"),
                    )
                )
            else:
                existing.name = fields.get("name", existing.name)
                existing.slug = fields.get("slug", existing.slug)
                existing.description = fields.get("description", existing.description)
        await self.session.flush()
        return category

    async def _apply_translations(
        self, product: Product, translations: dict[str, dict]
    ) -> None:
        for locale, fields in translations.items():
            existing = next((t for t in product.translations if t.locale == locale), None)
            if existing is None:
                product.translations.append(
                    ProductTranslation(
                        product_id=product.id,
                        locale=locale,
                        name=fields.get("name", ""),
                        slug=fields.get("slug", ""),
                        description=fields.get("description"),
                        seo_title=fields.get("seo_title"),
                        seo_description=fields.get("seo_description"),
                    )
                )
                continue
            existing.name = fields.get("name", existing.name)
            existing.slug = fields.get("slug", existing.slug)
            if "description" in fields:
                existing.description = fields["description"]
            if "seo_title" in fields:
                existing.seo_title = fields["seo_title"]
            if "seo_description" in fields:
                existing.seo_description = fields["seo_description"]
        await self.session.flush()

    @staticmethod
    def _status(raw: str | ProductStatus) -> ProductStatus:
        if isinstance(raw, ProductStatus):
            return raw
        try:
            return ProductStatus(str(raw).lower())
        except ValueError as exc:
            raise NotFoundError(
                message=f"unknown product status '{raw}'",
                code="INVALID_PRODUCT_STATUS",
                status_code=422,
            ) from exc
