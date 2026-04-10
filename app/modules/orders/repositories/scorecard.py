"""Data access for broker scorecards."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.orders.models.broker_scorecard import BrokerScorecardRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ScorecardRepository(BaseRepository):
    """CRUD for broker scorecard records."""

    async def get_by_broker(
        self,
        broker_id: str,
        instrument_class: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> BrokerScorecardRecord | None:
        async with self._session(session) as session:
            stmt = select(BrokerScorecardRecord).where(
                BrokerScorecardRecord.broker_id == broker_id,
            )
            if instrument_class is not None:
                stmt = stmt.where(
                    BrokerScorecardRecord.instrument_class == instrument_class,
                )
            else:
                stmt = stmt.where(BrokerScorecardRecord.instrument_class.is_(None))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[BrokerScorecardRecord]:
        async with self._session(session) as session:
            stmt = select(BrokerScorecardRecord).order_by(
                BrokerScorecardRecord.broker_id,
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def upsert(
        self,
        record: BrokerScorecardRecord,
        *,
        session: AsyncSession | None = None,
    ) -> BrokerScorecardRecord:
        async with self._session(session) as session:
            merged = await session.merge(record)
            await session.flush()
            await session.commit()
            await session.refresh(merged)
            return merged
