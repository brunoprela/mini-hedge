"""Risk engine data persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.risk_engine.models import (
    FactorExposureRecord,
    RiskSnapshotRecord,
    StressPositionImpactRecord,
    StressTestResultRecord,
    VaRContributionRecord,
    VaRResultRecord,
)

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory


class RiskRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    # -- Snapshots --

    async def save_snapshot(self, record: RiskSnapshotRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_latest_snapshot(self, portfolio_id: UUID) -> RiskSnapshotRecord | None:
        async with self._sf() as session:
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
    ) -> list[RiskSnapshotRecord]:
        async with self._sf() as session:
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

    # -- VaR results --

    async def save_var_result(
        self,
        result_record: VaRResultRecord,
        contributions: list[VaRContributionRecord],
    ) -> None:
        async with self._sf() as session:
            session.add(result_record)
            for c in contributions:
                session.add(c)
            await session.commit()

    async def get_latest_var(self, portfolio_id: UUID, method: str) -> VaRResultRecord | None:
        async with self._sf() as session:
            result = await session.execute(
                select(VaRResultRecord)
                .where(
                    VaRResultRecord.portfolio_id == str(portfolio_id),
                    VaRResultRecord.method == method,
                )
                .order_by(VaRResultRecord.calculated_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_var_contributions(self, var_result_id: str) -> list[VaRContributionRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(VaRContributionRecord).where(
                    VaRContributionRecord.var_result_id == var_result_id
                )
            )
            return list(result.scalars().all())

    # -- Stress tests --

    async def save_stress_result(
        self,
        result_record: StressTestResultRecord,
        impacts: list[StressPositionImpactRecord],
    ) -> None:
        async with self._sf() as session:
            session.add(result_record)
            for imp in impacts:
                session.add(imp)
            await session.commit()

    async def get_stress_results(self, portfolio_id: UUID) -> list[StressTestResultRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(StressTestResultRecord)
                .where(StressTestResultRecord.portfolio_id == str(portfolio_id))
                .order_by(StressTestResultRecord.calculated_at.desc())
                .limit(20)
            )
            return list(result.scalars().all())

    async def get_stress_impacts(self, stress_result_id: str) -> list[StressPositionImpactRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(StressPositionImpactRecord).where(
                    StressPositionImpactRecord.stress_result_id == stress_result_id
                )
            )
            return list(result.scalars().all())

    # -- Factor exposures --

    async def save_factor_exposures(self, records: list[FactorExposureRecord]) -> None:
        async with self._sf() as session:
            for r in records:
                session.add(r)
            await session.commit()

    async def get_factor_exposures(self, snapshot_id: str) -> list[FactorExposureRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(FactorExposureRecord).where(FactorExposureRecord.snapshot_id == snapshot_id)
            )
            return list(result.scalars().all())
