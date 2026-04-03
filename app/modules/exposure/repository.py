"""Exposure snapshot persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.exposure.models import ExposureSnapshotRecord

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory


class ExposureRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def save_snapshot(self, record: ExposureSnapshotRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_latest(self, portfolio_id: UUID) -> ExposureSnapshotRecord | None:
        async with self._sf() as session:
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
    ) -> list[ExposureSnapshotRecord]:
        async with self._sf() as session:
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
