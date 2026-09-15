from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.catalog.models import (
    Category,
    Media,
    Product,
    ProductCategory,
    ProductStatus,
    ProductTranslation,
)


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_product_id_by_slug(self, slug: str, locale: str) -> uuid.UUID | None:
        stmt = select(ProductTranslation.product_id).where(
            ProductTranslation.slug == slug, ProductTranslation.locale == locale
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get(self, product_id: uuid.UUID) -> Product | None:
        return await self.session.get(Product, product_id)

    async def list_published(
        self,
        limit: int,
        offset: int,
        category_id: uuid.UUID | None = None,
    ) -> list[Product]:
        stmt = (
            select(Product)
            .where(Product.status == ProductStatus.PUBLISHED)
            .order_by(Product.position, Product.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if category_id is not None:
            stmt = stmt.join(
                ProductCategory, ProductCategory.product_id == Product.id
            ).where(ProductCategory.category_id == category_id)
        return list((await self.session.execute(stmt)).scalars())

    async def count_published(self, category_id: uuid.UUID | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(Product)
            .where(Product.status == ProductStatus.PUBLISHED)
        )
        if category_id is not None:
            stmt = stmt.join(
                ProductCategory, ProductCategory.product_id == Product.id
            ).where(ProductCategory.category_id == category_id)
        return int((await self.session.execute(stmt)).scalar_one())

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[Product]:
        stmt = (
            select(Product)
            .order_by(Product.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def media_for(
        self, owner_type: str, owner_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[Media]]:
        if not owner_ids:
            return {}
        stmt = (
            select(Media)
            .where(Media.owner_type == owner_type, Media.owner_id.in_(owner_ids))
            .order_by(Media.position)
        )
        grouped: dict[uuid.UUID, list[Media]] = {}
        for row in (await self.session.execute(stmt)).scalars():
            grouped.setdefault(row.owner_id, []).append(row)
        return grouped

    async def list_categories(self) -> list[Category]:
        stmt = select(Category).order_by(Category.position, Category.path)
        return list((await self.session.execute(stmt)).scalars())

    async def get_category(self, category_id: uuid.UUID) -> Category | None:
        return await self.session.get(Category, category_id)

    async def category_by_slug(self, slug: str, locale: str) -> Category | None:
        from app.domain.catalog.models import CategoryTranslation

        stmt = (
            select(Category)
            .join(CategoryTranslation, CategoryTranslation.category_id == Category.id)
            .where(CategoryTranslation.slug == slug, CategoryTranslation.locale == locale)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
