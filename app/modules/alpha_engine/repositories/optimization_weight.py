"""Optimization weight persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.alpha_engine.models.optimization_weight import OptimizationWeightRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OptimizationWeightRepository(BaseRepository):
    """CRUD for OptimizationWeightRecord."""

    async def insert_batch(
        self, records: list[OptimizationWeightRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for w in records:
                session.add(w)
            await session.commit()

    async def get_by_run(
        self, run_id: str, *, session: AsyncSession | None = None
    ) -> list[OptimizationWeightRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(OptimizationWeightRecord).where(
                    OptimizationWeightRecord.optimization_run_id == run_id
                )
            )
            return list(result.scalars().all())
