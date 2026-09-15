from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.deps import CurrencyDep, I18nDep, RegionServiceDep, SessionDep
from app.core.security import AdminDep
from app.domain.currency.repository import CurrencyRepository
from app.domain.currency.schemas import (
    CurrencyRead,
    ExchangeRateOverride,
    ExchangeRateRead,
)
from app.domain.i18n.schemas import LocaleRead
from app.domain.region.schemas import RegionDetail

router = APIRouter(prefix="/settings", tags=["admin: settings"])


class RefreshResult(BaseModel):
    updated: int
    base: str


@router.get("/locales", response_model=list[LocaleRead])
async def list_locales(i18n: I18nDep, _: AdminDep) -> list[LocaleRead]:
    return [
        LocaleRead.model_validate(row) for row in await i18n.list_active_locales()
    ]


@router.get("/currencies", response_model=list[CurrencyRead])
async def list_currencies(currency: CurrencyDep, _: AdminDep) -> list[CurrencyRead]:
    return [
        CurrencyRead.model_validate(row) for row in await currency.list_active()
    ]


@router.get("/regions", response_model=list[RegionDetail])
async def list_regions(regions: RegionServiceDep, _: AdminDep) -> list[RegionDetail]:
    return [RegionDetail.from_region(region) for region in await regions.list_regions()]


@router.get("/exchange-rates", response_model=list[ExchangeRateRead])
async def list_exchange_rates(
    session: SessionDep, _: AdminDep, base: str = "USD"
) -> list[ExchangeRateRead]:
    rows = await CurrencyRepository(session).list_rates(base)
    return [ExchangeRateRead.model_validate(row) for row in rows]


@router.post("/exchange-rates/refresh", response_model=RefreshResult)
async def refresh_exchange_rates(
    session: SessionDep, currency: CurrencyDep, _: AdminDep, base: str = "USD"
) -> RefreshResult:
    updated = await currency.refresh_rates(base)
    await session.commit()
    return RefreshResult(updated=updated, base=base.upper())


@router.put("/exchange-rates", response_model=ExchangeRateRead)
async def override_exchange_rate(
    payload: ExchangeRateOverride,
    session: SessionDep,
    _: AdminDep,
) -> ExchangeRateRead:
    row = await CurrencyRepository(session).upsert_rate(
        payload.base_code, payload.quote_code, payload.rate, payload.source
    )
    await session.commit()
    return ExchangeRateRead.model_validate(row)
