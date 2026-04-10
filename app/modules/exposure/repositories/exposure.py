"""Exposure snapshot persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.exposure.models import ExposureSnapshotRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ExposureRepository(BaseRepository):
    async def save_snapshot(
        self, record: ExposureSnapshotRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_latest(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> ExposureSnapshotRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(ExposureSnapshotRecord)
                .where(ExposureSnapshotRecord.portfolio_id == str(portfolio_id))
                .order_by(ExposureSnapshotRecord.snapshot_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_history(
        self,
        portfolio_id: UUID,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> list[ExposureSnapshotRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(ExposureSnapshotRecord)
                .where(
                    ExposureSnapshotRecord.portfolio_id == str(portfolio_id),
                    ExposureSnapshotRecord.snapshot_at >= start,
                    ExposureSnapshotRecord.snapshot_at <= end,
                )
                .order_by(ExposureSnapshotRecord.snapshot_at.asc())
            )
            return list(result.scalars().all())
