"""Cart behaviour: anonymous creation, line management and totals."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import CartExpiredError, NotFoundError
from app.domain.cart.models import Cart, CartLine, CartStatus
from app.domain.cart.repository import CartRepository
from app.domain.catalog.models import ProductVariant
from app.domain.pricing.schemas import LineInput, PriceBreakdown
from app.domain.pricing.service import PricingService
from app.domain.region.service import RegionService

DEFAULT_TTL_DAYS = 30


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    """Tolerate naive datetimes, which is what SQLite hands back."""
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now


class CartService:
    def __init__(
        self,
        session: AsyncSession,
        pricing: PricingService | None = None,
        regions: RegionService | None = None,
    ) -> None:
        self.session = session
        self._repo = CartRepository(session)
        self._pricing = pricing or PricingService(session)
        self._regions = regions or RegionService(session)

    async def create(self, region_code: str, currency_code: str) -> Cart:
        now = datetime.now(UTC)
        cart = Cart(
            token=secrets.token_urlsafe(32),
            region_code=region_code,
            currency_code=currency_code.upper(),
            status=CartStatus.ACTIVE,
            expires_at=now + timedelta(days=DEFAULT_TTL_DAYS),
            # Explicit empty collection: a fresh instance has the attribute
            # unloaded, and the first access would trigger a lazy load that
            # async SQLAlchemy refuses to service.
            lines=[],
        )
        self._repo.add(cart)
        await self.session.flush()
        return cart

    async def get_by_token(self, token: str) -> Cart:
        cart = await self._repo.get_by_token(token)
        if cart is None:
            raise NotFoundError(message="cart not found", code="CART_NOT_FOUND")
        if cart.status != CartStatus.ACTIVE:
            raise CartExpiredError(
                message="cart is no longer active",
                details={"status": str(cart.status)},
            )
        if _is_expired(cart.expires_at, datetime.now(UTC)):
            raise CartExpiredError(message="cart has expired")
        return cart

    async def add_line(self, token: str, variant_id: uuid.UUID, quantity: int) -> Cart:
        if quantity <= 0:
            raise NotFoundError(
                message="quantity must be positive",
                code="INVALID_QUANTITY",
                status_code=422,
            )
        cart = await self.get_by_token(token)
        variant = await self.session.get(ProductVariant, variant_id)
        if variant is None:
            raise NotFoundError(message="variant not found", code="VARIANT_NOT_FOUND")

        unit_price = await self._pricing.unit_price(variant, cart.currency_code)

        existing = await self._repo.find_line(cart.id, variant_id)
        if existing is not None:
            existing.quantity += quantity
            existing.unit_price = unit_price
        else:
            line = CartLine(
                cart_id=cart.id,
                variant_id=variant_id,
                quantity=quantity,
                unit_price=unit_price,
                currency_code=cart.currency_code,
                position=len(cart.lines),
            )
            self._repo.add_line(line)
            cart.lines.append(line)

        await self.session.flush()
        await self.session.refresh(cart)
        return cart

    async def update_line(self, token: str, line_id: uuid.UUID, quantity: int) -> Cart:
        cart = await self.get_by_token(token)
        line = await self._repo.get_line(line_id)
        if line is None or line.cart_id != cart.id:
            raise NotFoundError(message="cart line not found", code="CART_LINE_NOT_FOUND")

        if quantity <= 0:
            cart.lines.remove(line)
            await self._repo.delete_line(line)
        else:
            line.quantity = quantity

        await self.session.flush()
        await self.session.refresh(cart)
        return cart

    async def remove_line(self, token: str, line_id: uuid.UUID) -> Cart:
        return await self.update_line(token, line_id, 0)

    async def set_email(self, cart: Cart, email: str) -> None:
        cart.email = email
        await self.session.flush()

    async def mark_converted(self, cart: Cart) -> None:
        cart.status = CartStatus.CONVERTED
        await self.session.flush()

    async def totals(self, token: str) -> PriceBreakdown:
        """Price the cart with *its own* region.

        The region is fixed when the cart is created, so tax and shipping must
        come from there rather than from whatever region the current request
        happens to negotiate — otherwise the cart page and the order would
        quote different totals for the same basket.
        """
        cart = await self.get_by_token(token)
        region = await self._regions.resolve_region(cart.region_code)
        lines = [
            LineInput(variant_id=line.variant_id, quantity=line.quantity)
            for line in cart.lines
        ]
        return await self._pricing.calculate(
            lines, region=region, currency_code=cart.currency_code
        )
