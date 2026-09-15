from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from app.core.config import settings
from app.core.deps import CartDep, RegionDep, RegionServiceDep, SessionDep
from app.domain.cart.schemas import (
    CartCreate,
    CartLineRead,
    CartLineUpdate,
    CartLineWrite,
    CartRead,
    CartTotalsRead,
)

router = APIRouter(prefix="/carts", tags=["store: carts"])

CART_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def _read(cart) -> CartRead:
    return CartRead.model_validate(cart)


@router.post("", response_model=CartRead, status_code=201)
async def create_cart(
    payload: CartCreate,
    response: Response,
    session: SessionDep,
    carts: CartDep,
    region: RegionDep,
    regions: RegionServiceDep,
) -> CartRead:
    # An explicit body region wins over the negotiated one: this request is
    # specifically about which region the new cart belongs to.
    target = await regions.resolve_region(payload.region) if payload.region else region
    cart = await carts.create(region_code=target.code, currency_code=target.currency_code)
    await session.commit()
    response.set_cookie(
        settings.cart_token_cookie,
        cart.token,
        httponly=True,
        samesite="lax",
        max_age=CART_COOKIE_MAX_AGE,
    )
    return _read(cart)


@router.get("/{token}", response_model=CartRead)
async def get_cart(token: str, carts: CartDep) -> CartRead:
    return _read(await carts.get_by_token(token))


@router.get("/{token}/totals", response_model=CartTotalsRead)
async def cart_totals(token: str, carts: CartDep) -> CartTotalsRead:
    breakdown = await carts.totals(token)
    return CartTotalsRead(
        currency=breakdown.currency,
        subtotal=breakdown.subtotal,
        shipping_fee=breakdown.shipping_fee,
        tax=breakdown.tax,
        total=breakdown.total,
    )


@router.post("/{token}/lines", response_model=CartRead)
async def add_line(
    token: str,
    payload: CartLineWrite,
    session: SessionDep,
    carts: CartDep,
) -> CartRead:
    cart = await carts.add_line(token, payload.variant_id, payload.quantity)
    await session.commit()
    return _read(cart)


@router.patch("/{token}/lines/{line_id}", response_model=CartRead)
async def update_line(
    token: str,
    line_id: uuid.UUID,
    payload: CartLineUpdate,
    session: SessionDep,
    carts: CartDep,
) -> CartRead:
    cart = await carts.update_line(token, line_id, payload.quantity)
    await session.commit()
    return _read(cart)


@router.delete("/{token}/lines/{line_id}", response_model=CartRead)
async def remove_line(
    token: str,
    line_id: uuid.UUID,
    session: SessionDep,
    carts: CartDep,
) -> CartRead:
    cart = await carts.remove_line(token, line_id)
    await session.commit()
    return _read(cart)


__all__ = ["CartLineRead", "router"]
