"""Checkout: turn a cart into an immutable order.

Everything happens inside the caller's transaction. If any step fails — stock,
pricing, payment intent — nothing is committed, so a customer can never end up
with a half-created order or stock reserved for a cart that failed.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError, PaymentFailedError
from app.domain.cart.service import CartService
from app.domain.catalog.models import ProductVariant
from app.domain.i18n.service import I18nService
from app.domain.inventory.service import InventoryService
from app.domain.order.models import Order, OrderLine
from app.domain.order.repository import OrderRepository
from app.domain.order.state_machine import OrderStatus, allowed_targets
from app.domain.payment.base import PaymentProvider
from app.domain.payment.mock import get_payment_provider
from app.domain.pricing.service import PricingService
from app.domain.region.service import RegionService

NUMBER_ATTEMPTS = 5


def _variant_label(variant: ProductVariant, locale: str, default_locale: str) -> str | None:
    parts: list[str] = []
    for link in variant.option_values:
        value = link.option_value
        if value is None:
            continue
        row = next((t for t in value.translations if t.locale == locale), None)
        if row is None:
            row = next((t for t in value.translations if t.locale == default_locale), None)
        if row is not None:
            parts.append(row.label)
    return " / ".join(parts) if parts else None


class OrderService:
    def __init__(
        self,
        session: AsyncSession,
        cart_service: CartService | None = None,
        inventory_service: InventoryService | None = None,
        pricing_service: PricingService | None = None,
        region_service: RegionService | None = None,
        i18n_service: I18nService | None = None,
    ) -> None:
        self.session = session
        self._repo = OrderRepository(session)
        self._carts = cart_service or CartService(session)
        self._inventory = inventory_service or InventoryService(session)
        self._pricing = pricing_service or PricingService(session)
        self._regions = region_service or RegionService(session)
        self._i18n = i18n_service or I18nService(session)

    async def _next_number(self) -> str:
        stamp = datetime.now(UTC).strftime("%y%m%d")
        for _ in range(NUMBER_ATTEMPTS):
            candidate = f"NS-{stamp}-{secrets.token_hex(3).upper()}"
            if not await self._repo.number_exists(candidate):
                return candidate
        # Fall back to a longer random suffix rather than failing checkout.
        return f"NS-{stamp}-{secrets.token_hex(6).upper()}"

    async def checkout(
        self,
        cart_token: str,
        email: str,
        shipping_address: dict,
        idempotency_key: str | None = None,
        locale: str | None = None,
        provider_code: str = "mock",
    ) -> Order:
        if idempotency_key:
            existing = await self._repo.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        cart = await self._carts.get_by_token(cart_token)
        if not cart.lines:
            raise NotFoundError(message="cart is empty", code="CART_EMPTY")

        region = await self._regions.resolve_region(cart.region_code)
        resolved_locale = await self._i18n.resolve_locale(locale)
        default_locale = await self._i18n.default_locale()

        variants = await self._load_variants([line.variant_id for line in cart.lines])

        breakdown = await self._pricing.calculate(
            [line_input(line) for line in cart.lines],
            region=region,
            currency_code=cart.currency_code,
        )

        order = Order(
            number=await self._next_number(),
            status=OrderStatus.DRAFT,
            region_code=region.code,
            currency_code=cart.currency_code,
            email=email,
            shipping_address=shipping_address,
            subtotal=breakdown.subtotal,
            shipping_fee=breakdown.shipping_fee,
            tax=breakdown.tax,
            total=breakdown.total,
            idempotency_key=idempotency_key,
            # Both collections are appended to below and must therefore exist
            # before the object turns persistent.
            lines=[],
            events=[],
        )

        for line in cart.lines:
            variant = variants.get(line.variant_id)
            if variant is None:
                raise NotFoundError(
                    message="a cart line references a missing variant",
                    code="VARIANT_NOT_FOUND",
                    details={"variant_id": str(line.variant_id)},
                )
            translation = await self._i18n.translate(variant.product.translations, resolved_locale)
            unit_price = await self._pricing.unit_price(variant, cart.currency_code)
            order.lines.append(
                OrderLine(
                    variant_id=variant.id,
                    product_name=translation.name if translation else variant.sku,
                    variant_label=_variant_label(variant, resolved_locale, default_locale),
                    sku=variant.sku,
                    unit_price=unit_price,
                    quantity=line.quantity,
                    line_total=unit_price * line.quantity,
                    currency_code=cart.currency_code,
                )
            )

        for line in cart.lines:
            await self._inventory.reserve(line.variant_id, line.quantity)

        self._repo.add(order)
        await self.session.flush()

        provider = self._payment_provider(provider_code)
        intent = await provider.create_intent(order)
        if intent.status == "failed":
            raise PaymentFailedError(message="payment intent could not be created")

        order.mark_awaiting_payment(f"intent:{intent.provider_ref}")
        await self._carts.set_email(cart, email)
        await self._carts.mark_converted(cart)
        await self.session.flush()
        return order

    async def get(self, number: str) -> Order:
        order = await self._repo.get_by_number(number)
        if order is None:
            raise NotFoundError(message="order not found", code="ORDER_NOT_FOUND")
        return order

    async def get_by_ref(self, ref: str) -> Order:
        """Resolve an order by primary key or by human-readable number."""
        order: Order | None = None
        try:
            order = await self._repo.get(uuid.UUID(ref))
        except (ValueError, AttributeError):
            order = None
        if order is None:
            order = await self._repo.get_by_number(ref)
        if order is None:
            raise NotFoundError(message="order not found", code="ORDER_NOT_FOUND")
        return order

    async def list_orders(
        self, status: OrderStatus | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Order], int]:
        orders = await self._repo.list(status=status, limit=limit, offset=offset)
        total = await self._repo.count(status=status)
        return orders, total

    async def pay(self, number: str, provider_code: str = "mock") -> Order:
        """Confirm the payment intent and commit reserved stock."""
        order = await self.get_by_ref(number)
        provider = self._payment_provider(provider_code)
        reference = next(
            (
                event.note.removeprefix("intent:")
                for event in reversed(order.events)
                if event.note and event.note.startswith("intent:")
            ),
            None,
        )
        if reference is None:
            raise PaymentFailedError(message="order has no payment intent")

        result = await provider.confirm(reference)
        if not result.success:
            raise PaymentFailedError(
                message="payment confirmation failed",
                details={"provider": provider_code, "reference": reference},
            )

        order.mark_paid(f"confirmed:{reference}")
        for line in order.lines:
            if line.variant_id is not None:
                await self._inventory.commit_reservation(line.variant_id, line.quantity)
        await self.session.flush()
        return order

    async def transition(
        self, ref: str, target: OrderStatus, note: str | None = None
    ) -> Order:
        order = await self.get_by_ref(ref)

        if target is OrderStatus.PAID:
            return await self.pay(ref)

        if target is OrderStatus.CANCELLED:
            order.cancel(note)
            for line in order.lines:
                if line.variant_id is not None:
                    await self._inventory.release(line.variant_id, line.quantity)
        elif target is OrderStatus.FULFILLED:
            order.mark_fulfilled(note)
        elif target is OrderStatus.COMPLETED:
            order.mark_completed(note)
        elif target is OrderStatus.REFUNDED:
            order.refund(note)
        elif target is OrderStatus.AWAITING_PAYMENT:
            order.mark_awaiting_payment(note)
        else:
            from app.domain.order.state_machine import assert_transition

            assert_transition(order.status, target)

        await self.session.flush()
        return order

    def allowed_next_statuses(self, order: Order) -> list[str]:
        return allowed_targets(order.status)

    async def _load_variants(
        self, variant_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ProductVariant]:
        if not variant_ids:
            return {}
        stmt = select(ProductVariant).where(ProductVariant.id.in_(list(variant_ids)))
        return {
            variant.id: variant for variant in (await self.session.execute(stmt)).scalars()
        }

    @staticmethod
    def _payment_provider(code: str) -> PaymentProvider:
        return get_payment_provider(code)


def line_input(line):
    from app.domain.pricing.schemas import LineInput

    return LineInput(variant_id=line.variant_id, quantity=line.quantity)
