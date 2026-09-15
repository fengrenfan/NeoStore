"""FastAPI dependency wiring.

Locale and region negotiation live here so no route handler re-implements them:
``?locale=`` beats ``Accept-Language``; ``?region=`` beats the ``X-Region``
header, which beats the cookie. Unknown values degrade to the configured default
instead of erroring.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.domain.cart.service import CartService
from app.domain.catalog.admin_service import CatalogAdminService
from app.domain.catalog.service import CatalogService
from app.domain.currency.service import CurrencyService
from app.domain.i18n.service import I18nService
from app.domain.inventory.service import InventoryService
from app.domain.order.service import OrderService
from app.domain.pricing.service import PricingService
from app.domain.region.models import Region
from app.domain.region.service import RegionService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_i18n_service(session: SessionDep) -> I18nService:
    return I18nService(session)


def get_region_service(session: SessionDep) -> RegionService:
    return RegionService(session)


def get_currency_service(session: SessionDep) -> CurrencyService:
    return CurrencyService(session)


def get_pricing_service(session: SessionDep) -> PricingService:
    return PricingService(session)


def get_catalog_service(session: SessionDep) -> CatalogService:
    return CatalogService(session)


def get_catalog_admin_service(session: SessionDep) -> CatalogAdminService:
    return CatalogAdminService(session)


def get_cart_service(session: SessionDep) -> CartService:
    return CartService(session)


def get_inventory_service(session: SessionDep) -> InventoryService:
    return InventoryService(session)


def get_order_service(session: SessionDep) -> OrderService:
    return OrderService(session)


async def get_locale(
    request: Request,
    session: SessionDep,
    locale: Annotated[str | None, Query(description="Explicit locale override")] = None,
) -> str:
    i18n = I18nService(session)
    if locale:
        return await i18n.resolve_locale(locale)
    return await i18n.resolve_from_accept_language(request.headers.get("accept-language"))


async def get_region(
    request: Request,
    session: SessionDep,
    region: Annotated[str | None, Query(description="Explicit region override")] = None,
) -> Region:
    code = (
        region
        or request.headers.get("x-region")
        or request.cookies.get(settings.region_cookie_name)
    )
    return await RegionService(session).resolve_region(code)


async def get_cart_token(
    request: Request,
    cart: Annotated[str | None, Query(description="Cart token override")] = None,
) -> str | None:
    return cart or request.cookies.get(settings.cart_token_cookie)


LocaleDep = Annotated[str, Depends(get_locale)]
RegionDep = Annotated[Region, Depends(get_region)]
CartTokenDep = Annotated[str | None, Depends(get_cart_token)]

I18nDep = Annotated[I18nService, Depends(get_i18n_service)]
RegionServiceDep = Annotated[RegionService, Depends(get_region_service)]
CurrencyDep = Annotated[CurrencyService, Depends(get_currency_service)]
PricingDep = Annotated[PricingService, Depends(get_pricing_service)]
CatalogDep = Annotated[CatalogService, Depends(get_catalog_service)]
CatalogAdminDep = Annotated[CatalogAdminService, Depends(get_catalog_admin_service)]
CartDep = Annotated[CartService, Depends(get_cart_service)]
InventoryDep = Annotated[InventoryService, Depends(get_inventory_service)]
OrderDep = Annotated[OrderService, Depends(get_order_service)]
