"""Data access for order fills."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.orders.models.order_fill import OrderFillRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrderFillRepository(BaseRepository):
    """CRUD for order fills."""

    async def insert_fill(
        self, fill: OrderFillRecord, *, session: AsyncSession | None = None
    ) -> OrderFillRecord:
        async with self._session(session) as session:
            session.add(fill)
            await session.flush()
            await session.commit()
            await session.refresh(fill)
            return fill

    async def get_fills(
        self, order_id: UUID, *, session: AsyncSession | None = None
    ) -> list[OrderFillRecord]:
        async with self._session(session) as session:
            stmt = (
                select(OrderFillRecord)
                .where(OrderFillRecord.order_id == str(order_id))
                .order_by(OrderFillRecord.filled_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
