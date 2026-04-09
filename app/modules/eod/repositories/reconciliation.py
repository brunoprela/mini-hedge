"""Reconciliation result persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.modules.eod.models.reconciliation import ReconciliationRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ReconciliationRepository(BaseRepository):
    """Data access for reconciliation results."""

    async def upsert(
        self,
        *,
        portfolio_id: str,
        business_date: date,
        total_positions: int,
        matched_positions: int,
        is_clean: bool,
        breaks: list[dict[str, Any]],
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(ReconciliationRecord).values(
                portfolio_id=portfolio_id,
                business_date=business_date,
                total_positions=total_positions,
                matched_positions=matched_positions,
                is_clean=is_clean,
                breaks=breaks,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=ReconciliationRecord.__table__.primary_key,  # type: ignore[arg-type]
                set_={
                    "total_positions": stmt.excluded.total_positions,
                    "matched_positions": stmt.excluded.matched_positions,
                    "is_clean": stmt.excluded.is_clean,
                    "breaks": stmt.excluded.breaks,
                },
            )
            await s.execute(stmt)
            await s.commit()

    async def get_by_date(
        self,
        portfolio_id: str,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> ReconciliationRecord | None:
        async with self._session(session) as s:
            stmt = select(ReconciliationRecord).where(
                ReconciliationRecord.portfolio_id == portfolio_id,
                ReconciliationRecord.business_date == business_date,
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_latest(
        self,
        portfolio_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ReconciliationRecord | None:
        async with self._session(session) as s:
            stmt = (
                select(ReconciliationRecord)
                .where(ReconciliationRecord.portfolio_id == portfolio_id)
                .order_by(ReconciliationRecord.business_date.desc())
                .limit(1)
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_portfolio(
        self,
        portfolio_id: str,
        *,
        limit: int = 30,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> list[ReconciliationRecord]:
        async with self._session(session) as s:
            stmt = (
                select(ReconciliationRecord)
                .where(ReconciliationRecord.portfolio_id == portfolio_id)
                .order_by(ReconciliationRecord.business_date.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())
