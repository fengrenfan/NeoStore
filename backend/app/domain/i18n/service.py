"""Locale negotiation and translation fallback.

The fallback chain is fixed project-wide: requested locale → default locale →
``None``. Callers never see partial fallback logic of their own.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.i18n.models import Locale, Translated
from app.domain.i18n.repository import LocaleRepository


class I18nService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._locales = LocaleRepository(session)
        self._default_locale: str | None = None

    async def list_active_locales(self) -> list[Locale]:
        return await self._locales.list_active()

    async def default_locale(self) -> str:
        if self._default_locale is None:
            self._default_locale = await self._locales.default_code() or settings.default_locale
        return self._default_locale

    async def resolve_locale(self, requested: str | None) -> str:
        """Normalise an incoming locale tag, falling back to the default."""
        default = await self.default_locale()
        if not requested:
            return default

        candidate = requested.strip()
        if not candidate:
            return default

        if await self._locales.get_code(candidate):
            return candidate

        # "en-GB" should land on the registered "en" when only that exists.
        base = candidate.replace("_", "-").split("-")[0]
        if base and base != candidate:
            found = await self._locales.find_by_prefix(base)
            if found:
                return found

        return default

    async def resolve_from_accept_language(self, header: str | None) -> str:
        """Walk an ``Accept-Language`` header and take the first match we host."""
        default = await self.default_locale()
        if not header:
            return default

        for raw in header.split(","):
            tag = raw.split(";")[0].strip()
            if not tag or tag == "*":
                continue
            if await self._locales.get_code(tag):
                return tag
            base = tag.replace("_", "-").split("-")[0]
            if base:
                found = await self._locales.find_by_prefix(base)
                if found:
                    return found

        return default

    async def translate(self, rows: Sequence[Translated], locale: str) -> Translated | None:
        """Pick the best translation row for ``locale``, or the default one."""
        if not rows:
            return None
        by_locale = {row.locale: row for row in rows}
        if locale in by_locale:
            return by_locale[locale]
        return by_locale.get(await self.default_locale())
