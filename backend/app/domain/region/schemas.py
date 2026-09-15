from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


class RegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    currency_code: str
    tax_rate: Decimal
    is_default: bool


class RegionDetail(RegionRead):
    locales: list[str] = []
    payment_methods: list[str] = []

    @classmethod
    def from_region(cls, region: Any) -> RegionDetail:
        """Build from a ``Region`` aggregate.

        Explicit rather than ``model_validate(region)``: the aggregate carries
        association rows, while this schema exposes plain locale and provider
        codes.
        """
        return cls(
            code=region.code,
            name=region.name,
            currency_code=region.currency_code,
            tax_rate=region.tax_rate,
            is_default=region.is_default,
            locales=[link.locale for link in region.locale_links],
            payment_methods=[
                link.provider_code
                for link in region.payment_method_links
                if link.is_active
            ],
        )


class RegionWrite(BaseModel):
    code: str
    name: str
    currency_code: str
    tax_rate: Decimal = Decimal("0")
    is_default: bool = False
    position: int = 0
    locales: list[str] = []
    payment_methods: list[str] = []
