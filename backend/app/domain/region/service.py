"""Region resolution. An unknown or absent region always degrades to the default."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError
from app.domain.region.models import Region
from app.domain.region.repository import RegionRepository


class RegionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = RegionRepository(session)

    async def list_regions(self) -> list[Region]:
        return await self._repo.list_all()

    async def resolve_region(self, code: str | None) -> Region:
        if code:
            region = await self._repo.get(code)
            if region is not None:
                return region
        fallback = await self._repo.get_default() or await self._repo.get_first()
        if fallback is None:
            raise NotFoundError(
                message="no region is configured",
                code="NO_REGION_CONFIGURED",
            )
        return fallback

    async def locales_for(self, region_code: str) -> list[str]:
        region = await self._repo.get(region_code)
        if region is None:
            return []
        return [link.locale for link in region.locale_links]

    async def available_payment_methods(self, region_code: str) -> list[str]:
        region = await self._repo.get(region_code)
        if region is None:
            return []
        return [
            link.provider_code for link in region.payment_method_links if link.is_active
        ]
