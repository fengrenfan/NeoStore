from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import CatalogAdminDep, SessionDep
from app.core.security import AdminDep
from app.domain.catalog.schemas import (
    AdminProductListPage,
    AdminProductRead,
    ProductPatch,
    ProductWrite,
)

router = APIRouter(prefix="/products", tags=["admin: products"])


class VariantPriceWrite(BaseModel):
    currency_code: str
    amount: Decimal


@router.get("", response_model=AdminProductListPage)
async def list_products(
    catalog: CatalogAdminDep,
    _: AdminDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminProductListPage:
    products, total = await catalog.list_products(limit=limit, offset=offset)
    return AdminProductListPage(
        items=[await catalog.to_admin_read(product) for product in products],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=AdminProductRead, status_code=201)
async def create_product(
    payload: ProductWrite,
    session: SessionDep,
    catalog: CatalogAdminDep,
    _: AdminDep,
) -> AdminProductRead:
    product = await catalog.create_product(payload)
    await session.commit()
    return await catalog.to_admin_read(product)


@router.get("/{product_id}", response_model=AdminProductRead)
async def get_product(
    product_id: uuid.UUID, catalog: CatalogAdminDep, _: AdminDep
) -> AdminProductRead:
    return await catalog.to_admin_read(await catalog.get_product(product_id))


@router.patch("/{product_id}", response_model=AdminProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductPatch,
    session: SessionDep,
    catalog: CatalogAdminDep,
    _: AdminDep,
) -> AdminProductRead:
    product = await catalog.update_product(product_id, payload)
    await session.commit()
    return await catalog.to_admin_read(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID, session: SessionDep, catalog: CatalogAdminDep, _: AdminDep
) -> None:
    await catalog.delete_product(product_id)
    await session.commit()


@router.put("/{product_id}/variants/{variant_id}/price", response_model=AdminProductRead)
async def set_variant_price(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    payload: VariantPriceWrite,
    session: SessionDep,
    catalog: CatalogAdminDep,
    _: AdminDep,
) -> AdminProductRead:
    await catalog.set_variant_price(variant_id, payload.currency_code, payload.amount)
    await session.commit()
    return await catalog.to_admin_read(await catalog.get_product(product_id))
