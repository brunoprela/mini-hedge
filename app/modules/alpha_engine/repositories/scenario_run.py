"""Scenario run persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.alpha_engine.models.scenario_run import ScenarioRunRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ScenarioRunRepository(BaseRepository):
    """CRUD for ScenarioRunRecord."""

    async def insert(self, record: ScenarioRunRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def list_by_portfolio(
        self, portfolio_id: UUID, limit: int = 20, *, session: AsyncSession | None = None
    ) -> list[ScenarioRunRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(ScenarioRunRecord)
                .where(ScenarioRunRecord.portfolio_id == str(portfolio_id))
                .order_by(ScenarioRunRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_by_id(
        self, scenario_id: str, *, session: AsyncSession | None = None
    ) -> ScenarioRunRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(ScenarioRunRecord).where(ScenarioRunRecord.id == scenario_id)
            )
            return result.scalar_one_or_none()
