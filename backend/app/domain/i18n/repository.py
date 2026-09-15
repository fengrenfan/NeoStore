from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.i18n.models import Locale


class LocaleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[Locale]:
        stmt = (
            select(Locale)
            .where(Locale.is_active.is_(True))
            .order_by(Locale.position, Locale.code)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def get_code(self, code: str) -> str | None:
        stmt = select(Locale.code).where(Locale.code == code, Locale.is_active.is_(True))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_by_prefix(self, prefix: str) -> str | None:
        stmt = (
            select(Locale.code)
            .where(Locale.code.ilike(f"{prefix}%"), Locale.is_active.is_(True))
            .order_by(Locale.position)
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def default_code(self) -> str | None:
        stmt = select(Locale.code).where(Locale.is_default.is_(True)).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, locale: Locale) -> Locale:
        existing = await self.session.get(Locale, locale.code)
        if existing is None:
            self.session.add(locale)
            await self.session.flush()
            return locale
        existing.name = locale.name
        existing.is_active = locale.is_active
        existing.is_default = locale.is_default
        existing.position = locale.position
        await self.session.flush()
        return existing
