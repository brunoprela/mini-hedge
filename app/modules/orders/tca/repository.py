"""Data access for TCA results."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.orders.models import TCAResultRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TCARepository(BaseRepository):
    """CRUD for TCAResultRecord."""

    async def save(
        self, record: TCAResultRecord, *, session: AsyncSession | None = None
    ) -> TCAResultRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_order_id(
        self, order_id: UUID, *, session: AsyncSession | None = None
    ) -> TCAResultRecord | None:
        async with self._session(session) as session:
            stmt = select(TCAResultRecord).where(TCAResultRecord.order_id == str(order_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_order_ids(
        self, order_ids: list[str], *, session: AsyncSession | None = None
    ) -> list[TCAResultRecord]:
        if not order_ids:
            return []
        async with self._session(session) as session:
            stmt = (
                select(TCAResultRecord)
                .where(TCAResultRecord.order_id.in_(order_ids))
                .order_by(TCAResultRecord.computed_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
