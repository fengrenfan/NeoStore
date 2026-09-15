from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.deps import CatalogAdminDep, SessionDep
from app.core.security import AdminDep
from app.domain.catalog.schemas import CategoryPatch, CategoryWrite

router = APIRouter(prefix="/categories", tags=["admin: categories"])


class CategoryTranslationRead(BaseModel):
    locale: str
    name: str
    slug: str


class CategoryRead(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    path: str
    translations: list[CategoryTranslationRead] = []


def _serialize(category) -> CategoryRead:
    return CategoryRead(
        id=category.id,
        parent_id=category.parent_id,
        path=category.path,
        translations=[
            CategoryTranslationRead(locale=row.locale, name=row.name, slug=row.slug)
            for row in category.translations
        ],
    )


@router.get("", response_model=list[CategoryRead])
async def list_categories(catalog: CatalogAdminDep, _: AdminDep) -> list[CategoryRead]:
    return [_serialize(row) for row in await catalog.list_categories()]


@router.post("", response_model=CategoryRead, status_code=201)
async def create_category(
    payload: CategoryWrite, session: SessionDep, catalog: CatalogAdminDep, _: AdminDep
) -> CategoryRead:
    category = await catalog.create_category(payload.translations, payload.parent_id)
    await session.commit()
    return _serialize(category)


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryPatch,
    session: SessionDep,
    catalog: CatalogAdminDep,
    _: AdminDep,
) -> CategoryRead:
    category = await catalog.upsert_category_translations(
        category_id, payload.translations or {}
    )
    await session.commit()
    return _serialize(category)
