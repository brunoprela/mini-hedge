"""Performance attribution data persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.attribution.models import (
    BrinsonFachlerRecord,
    BrinsonFachlerSectorRecord,
    CumulativeAttributionRecord,
    RiskBasedRecord,
    RiskFactorContributionRecord,
)

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory


class AttributionRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    # -- Brinson-Fachler --

    async def save_brinson_fachler(
        self,
        record: BrinsonFachlerRecord,
        sectors: list[BrinsonFachlerSectorRecord],
    ) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.flush()  # generate server-side id
            for s in sectors:
                s.bf_result_id = record.id
                session.add(s)
            await session.commit()

    async def get_brinson_fachler(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
    ) -> list[BrinsonFachlerRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(BrinsonFachlerRecord)
                .where(
                    BrinsonFachlerRecord.portfolio_id == str(portfolio_id),
                    BrinsonFachlerRecord.period_start >= start,
                    BrinsonFachlerRecord.period_end <= end,
                )
                .order_by(BrinsonFachlerRecord.period_start.asc())
            )
            return list(result.scalars().all())

    async def get_bf_sectors(self, bf_result_id: str) -> list[BrinsonFachlerSectorRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(BrinsonFachlerSectorRecord).where(
                    BrinsonFachlerSectorRecord.bf_result_id == bf_result_id
                )
            )
            return list(result.scalars().all())

    # -- Risk-based --

    async def save_risk_based(
        self,
        record: RiskBasedRecord,
        factors: list[RiskFactorContributionRecord],
    ) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.flush()  # generate server-side id
            for f in factors:
                f.rb_result_id = record.id
                session.add(f)
            await session.commit()

    async def get_risk_based(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
    ) -> list[RiskBasedRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(RiskBasedRecord)
                .where(
                    RiskBasedRecord.portfolio_id == str(portfolio_id),
                    RiskBasedRecord.period_start >= start,
                    RiskBasedRecord.period_end <= end,
                )
                .order_by(RiskBasedRecord.period_start.asc())
            )
            return list(result.scalars().all())

    async def get_risk_factors(self, rb_result_id: str) -> list[RiskFactorContributionRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(RiskFactorContributionRecord).where(
                    RiskFactorContributionRecord.rb_result_id == rb_result_id
                )
            )
            return list(result.scalars().all())

    # -- Cumulative --

    async def save_cumulative(self, record: CumulativeAttributionRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_latest_cumulative(self, portfolio_id: UUID) -> CumulativeAttributionRecord | None:
        async with self._sf() as session:
            result = await session.execute(
                select(CumulativeAttributionRecord)
                .where(CumulativeAttributionRecord.portfolio_id == str(portfolio_id))
                .order_by(CumulativeAttributionRecord.calculated_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
