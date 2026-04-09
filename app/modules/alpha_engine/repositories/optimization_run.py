"""Optimization run persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.alpha_engine.models.optimization_run import OptimizationRunRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OptimizationRunRepository(BaseRepository):
    """CRUD for OptimizationRunRecord."""

    async def save(
        self, record: OptimizationRunRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_many(
        self,
        portfolio_id: UUID,
        limit: int = 20,
        *,
        session: AsyncSession | None = None,
    ) -> list[OptimizationRunRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(OptimizationRunRecord)
                .where(OptimizationRunRecord.portfolio_id == str(portfolio_id))
                .order_by(OptimizationRunRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_by_id(
        self, run_id: str, *, session: AsyncSession | None = None
    ) -> OptimizationRunRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(OptimizationRunRecord).where(OptimizationRunRecord.id == run_id)
            )
            return result.scalar_one_or_none()
