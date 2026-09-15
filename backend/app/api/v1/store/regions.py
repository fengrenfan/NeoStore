from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import RegionServiceDep
from app.domain.region.schemas import RegionDetail

router = APIRouter(prefix="/regions", tags=["store: regions"])


@router.get("", response_model=list[RegionDetail])
async def list_regions(regions: RegionServiceDep) -> list[RegionDetail]:
    return [RegionDetail.from_region(region) for region in await regions.list_regions()]
