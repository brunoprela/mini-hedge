"""Alternative data point persistence layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.modules.alt_data.models.alt_data_point import AltDataPointRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


class AltDataPointRepository(BaseRepository):
    """CRUD operations for alternative data points."""

    async def insert_data_points(
        self, records: list[AltDataPointRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add_all(records)
            await s.commit()

    async def get_data_points(
        self,
        feed_id: str,
        *,
        instrument_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
        session: AsyncSession | None = None,
    ) -> list[AltDataPointRecord]:
        async with self._session(session) as s:
            stmt = select(AltDataPointRecord).where(AltDataPointRecord.feed_id == feed_id)
            if instrument_id is not None:
                stmt = stmt.where(AltDataPointRecord.instrument_id == instrument_id)
            if start is not None:
                stmt = stmt.where(AltDataPointRecord.timestamp >= start)
            if end is not None:
                stmt = stmt.where(AltDataPointRecord.timestamp <= end)
            stmt = stmt.order_by(AltDataPointRecord.timestamp.desc()).limit(limit)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_point(
        self,
        feed_id: str,
        instrument_id: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> AltDataPointRecord | None:
        async with self._session(session) as s:
            stmt = select(AltDataPointRecord).where(AltDataPointRecord.feed_id == feed_id)
            if instrument_id is not None:
                stmt = stmt.where(AltDataPointRecord.instrument_id == instrument_id)
            stmt = stmt.order_by(AltDataPointRecord.timestamp.desc()).limit(1)
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_summary(
        self, feed_id: str, *, session: AsyncSession | None = None
    ) -> dict[str, object]:
        """Return aggregated statistics for a feed."""
        async with self._session(session) as s:
            result = await s.execute(
                select(
                    func.count().label("data_points"),
                    func.avg(AltDataPointRecord.value).label("avg_value"),
                    func.min(AltDataPointRecord.value).label("min_value"),
                    func.max(AltDataPointRecord.value).label("max_value"),
                    func.min(AltDataPointRecord.timestamp).label("coverage_start"),
                    func.max(AltDataPointRecord.timestamp).label("coverage_end"),
                ).where(AltDataPointRecord.feed_id == feed_id)
            )
            row = result.one()
            return {
                "data_points": row.data_points,
                "avg_value": row.avg_value,
                "min_value": row.min_value,
                "max_value": row.max_value,
                "coverage_start": row.coverage_start,
                "coverage_end": row.coverage_end,
            }
