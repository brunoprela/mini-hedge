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
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RiskRepository(BaseRepository):
    # -- Snapshots --

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

    # -- VaR results --

    async def save_var_result(
        self,
        result_record: VaRResultRecord,
        contributions: list[VaRContributionRecord],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            session.add(result_record)
            await session.flush()
            for c in contributions:
                c.var_result_id = result_record.id
                session.add(c)
            await session.commit()

    async def get_latest_var(
        self, portfolio_id: UUID, method: str, *, session: AsyncSession | None = None
    ) -> VaRResultRecord | None:
        async with self._session(session) as session:
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

    async def get_var_contributions(
        self, var_result_id: str, *, session: AsyncSession | None = None
    ) -> list[VaRContributionRecord]:
        async with self._session(session) as session:
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
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            session.add(result_record)
            await session.flush()
            for imp in impacts:
                imp.stress_result_id = result_record.id
                session.add(imp)
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

    # -- Factor exposures --

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
