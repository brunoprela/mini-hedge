"""High water mark repository."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.fee_accounting.models.high_water_mark import HighWaterMarkRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class HighWaterMarkRepository(BaseRepository):
    """CRUD for high water marks."""

    async def get_latest(
        self,
        portfolio_id: UUID,
        *,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> HighWaterMarkRecord | None:
        async with self._session(session) as session:
            stmt = (
                select(HighWaterMarkRecord)
                .where(
                    HighWaterMarkRecord.portfolio_id == str(portfolio_id),
                    HighWaterMarkRecord.share_class == share_class,
                )
                .order_by(HighWaterMarkRecord.hwm_date.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def upsert(
        self, record: HighWaterMarkRecord, *, session: AsyncSession | None = None
    ) -> HighWaterMarkRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record
