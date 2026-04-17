"""Stress test result persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.risk_engine.models.stress_test_result import StressTestResultRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class StressTestResultRepository(BaseRepository):
    async def insert_stress_result(
        self,
        result_record: StressTestResultRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            session.add(result_record)
            await session.flush()
            await session.commit()

    async def get_stress_results(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[StressTestResultRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(StressTestResultRecord)
                .where(StressTestResultRecord.portfolio_id == str(portfolio_id))
                .order_by(StressTestResultRecord.calculated_at.desc())
                .limit(20)
            )
            return list(result.scalars().all())
