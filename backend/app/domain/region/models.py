"""Region: the aggregate binding a currency, its locales, tax and payments."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Region(Base):
    __tablename__ = "region"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currency.code"), nullable=False
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0")
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Named ``*_links`` on purpose: these are association rows, not locales or
    #: payment providers. The storefront schema exposes ``locales`` /
    #: ``payment_methods`` as plain strings, and a same-named ORM attribute would
    #: collide with it during ``model_validate``.
    locale_links: Mapped[list[RegionLocale]] = relationship(
        back_populates="region", cascade="all, delete-orphan", lazy="selectin"
    )
    payment_method_links: Mapped[list[RegionPaymentMethod]] = relationship(
        back_populates="region", cascade="all, delete-orphan", lazy="selectin"
    )


class RegionLocale(Base):
    __tablename__ = "region_locale"

    region_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("region.code", ondelete="CASCADE"), primary_key=True
    )
    locale: Mapped[str] = mapped_column(
        String(16), ForeignKey("locale.code", ondelete="CASCADE"), primary_key=True
    )
    region: Mapped[Region] = relationship(back_populates="locale_links")


class RegionPaymentMethod(Base):
    __tablename__ = "region_payment_method"

    region_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("region.code", ondelete="CASCADE"), primary_key=True
    )
    provider_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    region: Mapped[Region] = relationship(back_populates="payment_method_links")
