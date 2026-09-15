from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class VariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    label: str | None
    price: Decimal
    available: int


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    alt: str | None


class ProductCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    price: Decimal
    currency: str
    status: str
    image: str | None = None


class ProductDetailRead(ProductCardRead):
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    variants: list[VariantRead] = []
    media: list[MediaRead] = []


class ProductWrite(BaseModel):
    status: str = "draft"
    product_type: str = "default"
    base_price: Decimal = Decimal("0")
    base_currency: str = "USD"
    position: int = 0
    #: One entry per locale, e.g. ``{"en": {"name": "Neon Tee", "slug": "neon-tee"}}``
    translations: dict[str, dict] = {}
    variants: list[dict] = []
    media: list[dict] = []


class ProductPatch(BaseModel):
    status: str | None = None
    base_price: Decimal | None = None
    base_currency: str | None = None
    position: int | None = None
    translations: dict[str, dict] | None = None


class AdminTranslationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locale: str
    name: str
    slug: str
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None


class AdminVariantRead(BaseModel):
    id: uuid.UUID
    sku: str
    position: int
    prices: dict[str, Decimal] = {}
    available: int = 0


class AdminMediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    alt: str | None = None
    position: int
    is_primary: bool


class AdminProductRead(BaseModel):
    id: uuid.UUID
    status: str
    product_type: str
    base_price: Decimal
    base_currency: str
    position: int
    translations: list[AdminTranslationRead] = []
    variants: list[AdminVariantRead] = []
    media: list[AdminMediaRead] = []


class AdminProductListPage(BaseModel):
    items: list[AdminProductRead]
    total: int
    limit: int
    offset: int


class CategoryWrite(BaseModel):
    parent_id: uuid.UUID | None = None
    translations: dict[str, dict] = {}


class CategoryPatch(BaseModel):
    translations: dict[str, dict] | None = None
