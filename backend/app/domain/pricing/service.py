"""The single place where money is calculated.

Nothing else in the codebase multiplies or sums prices. API handlers and
frontends only ever display what this module produced.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.catalog.models import ProductVariant, VariantPrice
from app.domain.currency.money import round_money
from app.domain.currency.service import CurrencyService
from app.domain.pricing.schemas import LineInput, PriceBreakdown
from app.domain.region.models import Region

ZERO = Decimal("0")


class PricingService:
    def __init__(
        self, session: AsyncSession, currency_service: CurrencyService | None = None
    ) -> None:
        self.session = session
        self._currency = currency_service or CurrencyService(session)

    async def explicit_price(self, variant_id: uuid.UUID, currency_code: str) -> Decimal | None:
        stmt = select(VariantPrice.amount).where(
            VariantPrice.variant_id == variant_id,
            VariantPrice.currency_code == currency_code.upper(),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def unit_price(self, variant: ProductVariant, currency_code: str) -> Decimal:
        """Explicit price wins; otherwise the base price is converted."""
        places = await self._currency.decimal_places(currency_code)

        explicit = await self.explicit_price(variant.id, currency_code)
        if explicit is not None:
            return round_money(explicit, currency_code, places)

        product = variant.product
        converted = await self._currency.convert(
            product.base_price, product.base_currency, currency_code
        )
        return round_money(converted, currency_code, places)

    async def calculate(
        self,
        lines: Sequence[LineInput],
        region: Region,
        currency_code: str,
    ) -> PriceBreakdown:
        places = await self._currency.decimal_places(currency_code)

        variant_ids = [line.variant_id for line in lines]
        variants: dict[uuid.UUID, ProductVariant] = {}
        if variant_ids:
            stmt = select(ProductVariant).where(ProductVariant.id.in_(variant_ids))
            variants = {
                variant.id: variant for variant in (await self.session.execute(stmt)).scalars()
            }

        subtotal = ZERO
        for line in lines:
            variant = variants.get(line.variant_id)
            if variant is None:
                continue
            unit = await self.unit_price(variant, currency_code)
            subtotal += unit * line.quantity
        subtotal = round_money(subtotal, currency_code, places)

        shipping_fee = round_money(
            self._shipping_fee(subtotal, currency_code), currency_code, places
        )
        taxable = subtotal + shipping_fee
        tax = round_money(taxable * Decimal(region.tax_rate), currency_code, places)
        total = round_money(subtotal + shipping_fee + tax, currency_code, places)

        return PriceBreakdown(
            currency=currency_code.upper(),
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            tax=tax,
            total=total,
        )

    def _shipping_fee(self, subtotal: Decimal, currency_code: str) -> Decimal:
        """Flat shipping, waived above a threshold.

        Deliberately trivial for the MVP; a rule engine would replace this
        method without touching its callers.
        """
        threshold = Decimal("100") if currency_code.upper() != "JPY" else Decimal("10000")
        flat = Decimal("9.90") if currency_code.upper() != "JPY" else Decimal("990")
        return ZERO if subtotal >= threshold else flat
