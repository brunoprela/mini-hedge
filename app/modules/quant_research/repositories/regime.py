"""Regime detection snapshot persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.quant_research.models.regime_snapshot import RegimeSnapshotRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RegimeRepository(BaseRepository):
    """Persistence for regime detection snapshots."""

    async def save_snapshot(
        self, record: RegimeSnapshotRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_latest(
        self, *, session: AsyncSession | None = None
    ) -> RegimeSnapshotRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(RegimeSnapshotRecord)
                .order_by(RegimeSnapshotRecord.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_history(
        self, *, limit: int = 100, session: AsyncSession | None = None
    ) -> list[RegimeSnapshotRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(RegimeSnapshotRecord)
                .order_by(RegimeSnapshotRecord.start_date.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
