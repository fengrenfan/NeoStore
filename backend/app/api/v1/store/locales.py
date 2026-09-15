from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import I18nDep
from app.domain.i18n.schemas import LocaleRead

router = APIRouter(prefix="/locales", tags=["store: locales"])


@router.get("", response_model=list[LocaleRead])
async def list_locales(i18n: I18nDep) -> list[LocaleRead]:
    locales = await i18n.list_active_locales()
    return [LocaleRead.model_validate(row) for row in locales]
