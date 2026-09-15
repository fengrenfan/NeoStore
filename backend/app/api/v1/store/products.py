from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.core.deps import CatalogDep, LocaleDep, RegionDep
from app.domain.catalog.schemas import ProductCardRead, ProductDetailRead

router = APIRouter(prefix="/products", tags=["store: products"])


@router.get("", response_model=list[ProductCardRead])
async def list_products(
    response: Response,
    catalog: CatalogDep,
    locale: LocaleDep,
    region: RegionDep,
    category: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProductCardRead]:
    cards, total = await catalog.list_products(
        locale=locale,
        region=region,
        category_id=category,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Content-Language"] = locale
    response.headers["X-Currency"] = region.currency_code
    return [ProductCardRead.model_validate(card) for card in cards]


@router.get("/{slug}", response_model=ProductDetailRead)
async def get_product(
    slug: str,
    response: Response,
    catalog: CatalogDep,
    locale: LocaleDep,
    region: RegionDep,
) -> ProductDetailRead:
    detail = await catalog.get_product_by_slug(slug, locale=locale, region=region)
    response.headers["Content-Language"] = locale
    response.headers["X-Currency"] = detail.currency
    return ProductDetailRead.model_validate(detail)
