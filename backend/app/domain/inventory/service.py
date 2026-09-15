"""Reserve / release / commit stock without ever overselling.

Reservation is the mechanism that ties an order to physical stock before
payment. ``reserved`` counts units promised to unpaid orders; ``quantity`` is
what physically exists. Available stock is the difference.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import InsufficientStockError, NotFoundError
from app.domain.inventory.models import InventoryItem, StockMovement
from app.domain.inventory.repository import InventoryRepository


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = InventoryRepository(session)

    async def ensure_item(self, variant_id: uuid.UUID, quantity: int = 0) -> InventoryItem:
        item = await self._repo.get(variant_id)
        if item is None:
            item = InventoryItem(variant_id=variant_id, quantity=quantity, reserved=0)
            self.session.add(item)
            await self.session.flush()
        return item

    async def available(self, variant_id: uuid.UUID) -> int:
        item = await self._repo.get(variant_id)
        return 0 if item is None else item.available

    async def reserve(self, variant_id: uuid.UUID, quantity: int) -> None:
        if quantity <= 0:
            raise InsufficientStockError(
                message="reservation quantity must be positive",
                code="INVALID_QUANTITY",
                details={"variant_id": str(variant_id), "quantity": quantity},
            )

        item = await self._repo.get_for_update(variant_id)
        if item is None:
            raise InsufficientStockError(
                message="variant has no stock record",
                details={"variant_id": str(variant_id)},
            )
        if item.available < quantity:
            raise InsufficientStockError(
                message="not enough stock available",
                details={
                    "variant_id": str(variant_id),
                    "requested": quantity,
                    "available": item.available,
                },
            )

        item.reserved += quantity
        self._record(variant_id, quantity, "reserve")
        await self.session.flush()

    async def release(self, variant_id: uuid.UUID, quantity: int) -> None:
        """Give reserved units back without touching physical stock."""
        if quantity <= 0:
            return
        item = await self._repo.get_for_update(variant_id)
        if item is None:
            raise NotFoundError(
                message="variant has no stock record",
                details={"variant_id": str(variant_id)},
            )
        item.reserved = max(0, item.reserved - quantity)
        self._record(variant_id, -quantity, "release")
        await self.session.flush()

    async def commit_reservation(self, variant_id: uuid.UUID, quantity: int) -> None:
        """Turn a reservation into a real deduction once payment lands."""
        if quantity <= 0:
            return
        item = await self._repo.get_for_update(variant_id)
        if item is None:
            raise NotFoundError(
                message="variant has no stock record",
                details={"variant_id": str(variant_id)},
            )
        item.reserved = max(0, item.reserved - quantity)
        item.quantity = max(0, item.quantity - quantity)
        self._record(variant_id, -quantity, "commit")
        await self.session.flush()

    async def adjust(
        self, variant_id: uuid.UUID, delta: int, reason: str = "manual", note: str | None = None
    ) -> InventoryItem:
        """Manual stock correction from the admin dashboard."""
        item = await self._repo.get_for_update(variant_id)
        if item is None:
            item = InventoryItem(variant_id=variant_id, quantity=0, reserved=0)
            self.session.add(item)
            await self.session.flush()
        new_quantity = item.quantity + delta
        if new_quantity < item.reserved:
            raise InsufficientStockError(
                message="adjustment would put stock below what is reserved",
                details={
                    "variant_id": str(variant_id),
                    "quantity_after": new_quantity,
                    "reserved": item.reserved,
                },
            )
        item.quantity = max(0, new_quantity)
        self._record(variant_id, delta, reason, note)
        await self.session.flush()
        return item

    def _record(
        self, variant_id: uuid.UUID, delta: int, reason: str, note: str | None = None
    ) -> None:
        self.session.add(
            StockMovement(variant_id=variant_id, delta=delta, reason=reason, note=note)
        )
