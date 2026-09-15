from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.inventory.models import InventoryItem


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, variant_id: uuid.UUID) -> InventoryItem | None:
        return await self.session.get(InventoryItem, variant_id)

    async def get_for_update(self, variant_id: uuid.UUID) -> InventoryItem | None:
        """Lock the row so concurrent checkouts cannot both pass the guard.

        ``FOR UPDATE`` is a no-op on SQLite; that is why the oversell test is
        gated on the PostgreSQL dialect.
        """
        stmt = (
            select(InventoryItem)
            .where(InventoryItem.variant_id == variant_id)
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_variants(self, variant_ids: list[uuid.UUID]) -> list[InventoryItem]:
        if not variant_ids:
            return []
        stmt = select(InventoryItem).where(InventoryItem.variant_id.in_(variant_ids))
        return list((await self.session.execute(stmt)).scalars())
