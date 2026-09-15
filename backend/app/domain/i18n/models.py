"""Locale registry and the mixin used by every ``<entity>_translation`` table."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.base import Base


@runtime_checkable
class Translated(Protocol):
    """Anything carrying a ``locale`` attribute can be resolved by I18nService."""

    locale: str


class TranslationMixin:
    """Declares the ``locale`` half of a translation table's composite key.

    Subclasses declare their own ``__tablename__``, the owning entity's foreign
    key column (the other half of the primary key) and a unique constraint on
    ``(owner_id, locale)``.
    """

    @declared_attr
    def locale(cls) -> Mapped[str]:  # noqa: N805
        return mapped_column(
            String(16),
            ForeignKey("locale.code", ondelete="CASCADE"),
            primary_key=True,
        )


class Locale(Base):
    __tablename__ = "locale"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Locale {self.code}>"
