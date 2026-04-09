"""Risk snapshot persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.risk_engine.models.risk_snapshot import RiskSnapshotRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RiskSnapshotRepository(BaseRepository):
    async def save_snapshot(
        self, record: RiskSnapshotRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_latest_snapshot(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> RiskSnapshotRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(RiskSnapshotRecord)
                .where(RiskSnapshotRecord.portfolio_id == str(portfolio_id))
                .order_by(RiskSnapshotRecord.snapshot_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_snapshot_history(
        self,
        portfolio_id: UUID,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> list[RiskSnapshotRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(RiskSnapshotRecord)
                .where(
                    RiskSnapshotRecord.portfolio_id == str(portfolio_id),
                    RiskSnapshotRecord.snapshot_at >= start,
                    RiskSnapshotRecord.snapshot_at <= end,
                )
                .order_by(RiskSnapshotRecord.snapshot_at.asc())
            )
            return list(result.scalars().all())
