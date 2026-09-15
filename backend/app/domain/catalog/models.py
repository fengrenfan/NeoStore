"""Catalog: products, variants, SKUs, options, categories, media and per-currency prices.

Localized text always lives in a ``*_translation`` table keyed by
``(owner_id, locale)`` so a new language is a data change, never a migration.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Money, TimestampMixin, str_enum
from app.domain.i18n.models import TranslationMixin


class ProductStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Product(Base, TimestampMixin):
    __tablename__ = "product"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[ProductStatus] = mapped_column(
        str_enum(ProductStatus, "product_status"),
        nullable=False,
        default=ProductStatus.DRAFT,
        index=True,
    )
    product_type: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    #: Fallback price used when no explicit ``variant_price`` exists for a currency.
    base_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    translations: Mapped[list[ProductTranslation]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductVariant.position",
    )


class ProductTranslation(Base, TranslationMixin):
    __tablename__ = "product_translation"
    __table_args__ = (
        UniqueConstraint("locale", "slug", name="uq_product_translation_locale_slug"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    product: Mapped[Product] = relationship(back_populates="translations")


class ProductVariant(Base):
    """The smallest sellable unit. Stock and price hang off this."""

    __tablename__ = "product_variant"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Eager-loaded: pricing reads ``variant.product.base_price`` and must never
    #: trigger a lazy load inside an async session.
    product: Mapped[Product] = relationship(back_populates="variants", lazy="selectin")
    prices: Mapped[list[VariantPrice]] = relationship(
        back_populates="variant", cascade="all, delete-orphan", lazy="selectin"
    )
    option_values: Mapped[list[VariantOptionValue]] = relationship(
        back_populates="variant", cascade="all, delete-orphan", lazy="selectin"
    )


class VariantPrice(Base):
    """Explicit per-currency price. Absence means "convert ``base_price``"."""

    __tablename__ = "variant_price"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variant.id", ondelete="CASCADE"), primary_key=True
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), primary_key=True
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)

    variant: Mapped[ProductVariant] = relationship(back_populates="prices")


class ProductOption(Base):
    __tablename__ = "product_option"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    translations: Mapped[list[ProductOptionTranslation]] = relationship(
        back_populates="option", cascade="all, delete-orphan", lazy="selectin"
    )
    values: Mapped[list[OptionValue]] = relationship(
        back_populates="option",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OptionValue.position",
    )


class ProductOptionTranslation(Base, TranslationMixin):
    __tablename__ = "product_option_translation"

    option_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_option.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    option: Mapped[ProductOption] = relationship(back_populates="translations")


class OptionValue(Base):
    __tablename__ = "option_value"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    option_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_option.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    option: Mapped[ProductOption] = relationship(back_populates="values")
    translations: Mapped[list[OptionValueTranslation]] = relationship(
        back_populates="value", cascade="all, delete-orphan", lazy="selectin"
    )


class OptionValueTranslation(Base, TranslationMixin):
    __tablename__ = "option_value_translation"

    option_value_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("option_value.id", ondelete="CASCADE"), primary_key=True
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)

    value: Mapped[OptionValue] = relationship(back_populates="translations")


class VariantOptionValue(Base):
    __tablename__ = "variant_option_value"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variant.id", ondelete="CASCADE"), primary_key=True
    )
    option_value_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("option_value.id", ondelete="CASCADE"), primary_key=True
    )

    variant: Mapped[ProductVariant] = relationship(back_populates="option_values")
    option_value: Mapped[OptionValue] = relationship(lazy="selectin")


class Category(Base):
    __tablename__ = "category"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("category.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Materialised path such as ``"/<root_id>/<child_id>/"`` for subtree queries.
    path: Mapped[str] = mapped_column(String(512), nullable=False, default="/")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    translations: Mapped[list[CategoryTranslation]] = relationship(
        back_populates="category", cascade="all, delete-orphan", lazy="selectin"
    )


class CategoryTranslation(Base, TranslationMixin):
    __tablename__ = "category_translation"
    __table_args__ = (
        UniqueConstraint("locale", "slug", name="uq_category_translation_locale_slug"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("category.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    category: Mapped[Category] = relationship(back_populates="translations")


class ProductCategory(Base):
    __tablename__ = "product_category"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("category.id", ondelete="CASCADE"), primary_key=True
    )


class Media(Base):
    """Polymorphic attachment row shared by products and categories."""

    __tablename__ = "media"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    alt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
