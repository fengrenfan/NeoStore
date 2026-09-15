from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order.models import Order
from app.domain.order.state_machine import OrderStatus


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, order_id: uuid.UUID) -> Order | None:
        return await self.session.get(Order, order_id)

    async def get_by_number(self, number: str) -> Order | None:
        stmt = select(Order).where(Order.number == number)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        stmt = select(Order).where(Order.idempotency_key == key)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def number_exists(self, number: str) -> bool:
        stmt = select(Order.id).where(Order.number == number).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def list(
        self, status: OrderStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Order]:
        stmt = select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(Order.status == status)
        return list((await self.session.execute(stmt)).scalars())

    async def count(self, status: OrderStatus | None = None) -> int:
        stmt = select(func.count()).select_from(Order)
        if status is not None:
            stmt = stmt.where(Order.status == status)
        return int((await self.session.execute(stmt)).scalar_one())

    def add(self, order: Order) -> None:
        self.session.add(order)
