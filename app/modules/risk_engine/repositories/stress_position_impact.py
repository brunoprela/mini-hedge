"""Stress position impact persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.risk_engine.models.stress_position_impact import StressPositionImpactRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class StressPositionImpactRepository(BaseRepository):
    async def save_impacts(
        self,
        impacts: list[StressPositionImpactRecord],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            for imp in impacts:
                session.add(imp)
            await session.commit()

    async def get_stress_impacts(
        self, stress_result_id: str, *, session: AsyncSession | None = None
    ) -> list[StressPositionImpactRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(StressPositionImpactRecord).where(
                    StressPositionImpactRecord.stress_result_id == stress_result_id
                )
            )
            return list(result.scalars().all())
