"""Alpha engine data persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.alpha_engine.models import (
    OptimizationRunRecord,
    OptimizationWeightRecord,
    OrderIntentRecord,
    ScenarioRunRecord,
)

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory


class AlphaRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    # -- Scenario runs --

    async def save_scenario(self, record: ScenarioRunRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_scenarios(self, portfolio_id: UUID, limit: int = 20) -> list[ScenarioRunRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(ScenarioRunRecord)
                .where(ScenarioRunRecord.portfolio_id == str(portfolio_id))
                .order_by(ScenarioRunRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_scenario(self, scenario_id: str) -> ScenarioRunRecord | None:
        async with self._sf() as session:
            result = await session.execute(
                select(ScenarioRunRecord).where(ScenarioRunRecord.id == scenario_id)
            )
            return result.scalar_one_or_none()

    # -- Optimization runs --

    async def save_optimization(
        self,
        record: OptimizationRunRecord,
        weights: list[OptimizationWeightRecord],
        intents: list[OrderIntentRecord],
    ) -> None:
        async with self._sf() as session:
            session.add(record)
            for w in weights:
                session.add(w)
            for i in intents:
                session.add(i)
            await session.commit()

    async def get_optimizations(
        self, portfolio_id: UUID, limit: int = 20
    ) -> list[OptimizationRunRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(OptimizationRunRecord)
                .where(OptimizationRunRecord.portfolio_id == str(portfolio_id))
                .order_by(OptimizationRunRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_optimization(self, run_id: str) -> OptimizationRunRecord | None:
        async with self._sf() as session:
            result = await session.execute(
                select(OptimizationRunRecord).where(OptimizationRunRecord.id == run_id)
            )
            return result.scalar_one_or_none()

    async def get_optimization_weights(self, run_id: str) -> list[OptimizationWeightRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(OptimizationWeightRecord).where(
                    OptimizationWeightRecord.optimization_run_id == run_id
                )
            )
            return list(result.scalars().all())

    # -- Order intents --

    async def get_intents(self, portfolio_id: UUID) -> list[OrderIntentRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(OrderIntentRecord)
                .where(
                    OrderIntentRecord.portfolio_id == str(portfolio_id),
                    OrderIntentRecord.status == "draft",
                )
                .order_by(OrderIntentRecord.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_intents_by_run(self, run_id: str) -> list[OrderIntentRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(OrderIntentRecord).where(OrderIntentRecord.optimization_run_id == run_id)
            )
            return list(result.scalars().all())

    async def update_intent_status(self, intent_id: str, status: str) -> None:
        async with self._sf() as session:
            await session.execute(
                update(OrderIntentRecord)
                .where(OrderIntentRecord.id == intent_id)
                .values(status=status)
            )
            await session.commit()
