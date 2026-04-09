"""Factor exposure persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.risk_engine.models.factor_exposure import FactorExposureRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FactorExposureRepository(BaseRepository):
    async def save_factor_exposures(
        self, records: list[FactorExposureRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for r in records:
                session.add(r)
            await session.commit()

    async def get_factor_exposures(
        self, snapshot_id: str, *, session: AsyncSession | None = None
    ) -> list[FactorExposureRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(FactorExposureRecord).where(FactorExposureRecord.snapshot_id == snapshot_id)
            )
            return list(result.scalars().all())
