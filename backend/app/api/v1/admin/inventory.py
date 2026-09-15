from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.deps import InventoryDep, SessionDep
from app.core.security import AdminDep
from app.domain.order.schemas import InventoryAdjustment

router = APIRouter(prefix="/inventory", tags=["admin: inventory"])


class InventoryRead(BaseModel):
    variant_id: uuid.UUID
    quantity: int
    reserved: int
    available: int


@router.get("/{variant_id}", response_model=InventoryRead)
async def get_inventory(
    variant_id: uuid.UUID, inventory: InventoryDep, _: AdminDep
) -> InventoryRead:
    item = await inventory.ensure_item(variant_id)
    return InventoryRead(
        variant_id=variant_id,
        quantity=item.quantity,
        reserved=item.reserved,
        available=item.available,
    )


@router.post("/{variant_id}/adjust", response_model=InventoryRead)
async def adjust_inventory(
    variant_id: uuid.UUID,
    payload: InventoryAdjustment,
    session: SessionDep,
    inventory: InventoryDep,
    _: AdminDep,
) -> InventoryRead:
    item = await inventory.adjust(
        variant_id, payload.delta, reason=payload.reason, note=payload.note
    )
    await session.commit()
    return InventoryRead(
        variant_id=variant_id,
        quantity=item.quantity,
        reserved=item.reserved,
        available=item.available,
    )
