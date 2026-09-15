from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.region.models import Region


class RegionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, code: str) -> Region | None:
        return await self.session.get(Region, code)

    async def list_all(self) -> list[Region]:
        stmt = select(Region).order_by(Region.position, Region.code)
        return list((await self.session.execute(stmt)).scalars())

    async def get_default(self) -> Region | None:
        stmt = select(Region).where(Region.is_default.is_(True)).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_first(self) -> Region | None:
        stmt = select(Region).order_by(Region.position, Region.code).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, region: Region) -> Region:
        existing = await self.session.get(Region, region.code)
        if existing is None:
            self.session.add(region)
            await self.session.flush()
            return region
        existing.name = region.name
        existing.currency_code = region.currency_code
        existing.tax_rate = region.tax_rate
        existing.is_default = region.is_default
        existing.position = region.position
        await self.session.flush()
        return existing
