"""Data access for EOD runs and steps."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.modules.eod.models.eod_run import EODRunRecord
from app.modules.eod.models.eod_run_step import EODRunStepRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EODRunRepository(BaseRepository):
    """Data access for EOD runs and steps."""

    async def create_run(
        self,
        *,
        run_id: str,
        business_date: date,
        fund_slug: str,
        started_at: datetime,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            record = EODRunRecord(
                run_id=run_id,
                business_date=business_date,
                fund_slug=fund_slug,
                started_at=started_at,
                is_successful=False,
            )
            s.add(record)
            await s.commit()

    async def complete_run(
        self,
        run_id: str,
        *,
        is_successful: bool,
        completed_at: datetime,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = (
                update(EODRunRecord)
                .where(EODRunRecord.run_id == run_id)
                .values(is_successful=is_successful, completed_at=completed_at)
            )
            await s.execute(stmt)
            await s.commit()

    async def get_latest_run(
        self,
        business_date: date,
        fund_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> EODRunRecord | None:
        async with self._session(session) as s:
            stmt = (
                select(EODRunRecord)
                .where(
                    EODRunRecord.business_date == business_date,
                    EODRunRecord.fund_slug == fund_slug,
                )
                .order_by(EODRunRecord.started_at.desc())
                .limit(1)
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_run_history(
        self,
        fund_slug: str,
        *,
        limit: int = 20,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> list[EODRunRecord]:
        async with self._session(session) as s:
            stmt = (
                select(EODRunRecord)
                .where(EODRunRecord.fund_slug == fund_slug)
                .order_by(EODRunRecord.started_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def save_step(
        self,
        *,
        run_id: str,
        step: str,
        status: str,
        started_at: datetime,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(EODRunStepRecord).values(
                run_id=run_id,
                step=step,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                error_message=error_message,
                details=details,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=EODRunStepRecord.__table__.primary_key,  # type: ignore[arg-type]
                set_={
                    "status": stmt.excluded.status,
                    "completed_at": stmt.excluded.completed_at,
                    "error_message": stmt.excluded.error_message,
                    "details": stmt.excluded.details,
                },
            )
            await s.execute(stmt)
            await s.commit()

    async def get_steps(
        self, run_id: str, *, session: AsyncSession | None = None
    ) -> list[EODRunStepRecord]:
        async with self._session(session) as s:
            stmt = select(EODRunStepRecord).where(EODRunStepRecord.run_id == run_id)
            result = await s.execute(stmt)
            return list(result.scalars().all())
