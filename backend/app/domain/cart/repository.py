from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cart.models import Cart, CartLine


class CartRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, cart_id: uuid.UUID) -> Cart | None:
        return await self.session.get(Cart, cart_id)

    async def get_by_token(self, token: str) -> Cart | None:
        stmt = select(Cart).where(Cart.token == token)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_line(self, line_id: uuid.UUID) -> CartLine | None:
        return await self.session.get(CartLine, line_id)

    async def find_line(self, cart_id: uuid.UUID, variant_id: uuid.UUID) -> CartLine | None:
        stmt = select(CartLine).where(
            CartLine.cart_id == cart_id, CartLine.variant_id == variant_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add(self, cart: Cart) -> None:
        self.session.add(cart)

    def add_line(self, line: CartLine) -> None:
        self.session.add(line)

    async def delete_line(self, line: CartLine) -> None:
        await self.session.delete(line)
        await self.session.flush()
