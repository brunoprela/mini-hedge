"""Data access for EOD processing tables."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.modules.eod.models import (
    EODRunRecord,
    EODRunStepRecord,
    FinalizedPriceRecord,
    NAVSnapshotRecord,
    PnLSnapshotRecord,
    ReconciliationRecord,
)
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
                constraint=EODRunStepRecord.__table__.primary_key,
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


class FinalizedPriceRepository(BaseRepository):
    """Data access for locked closing prices."""

    async def upsert_price(
        self,
        *,
        instrument_id: str,
        business_date: date,
        close_price: Any,
        source: str,
        finalized_by: str,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(FinalizedPriceRecord).values(
                instrument_id=instrument_id,
                business_date=business_date,
                close_price=close_price,
                source=source,
                finalized_by=finalized_by,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=FinalizedPriceRecord.__table__.primary_key,
                set_={
                    "close_price": stmt.excluded.close_price,
                    "source": stmt.excluded.source,
                },
            )
            await s.execute(stmt)
            await s.commit()

    async def get_prices(
        self, business_date: date, *, session: AsyncSession | None = None
    ) -> list[FinalizedPriceRecord]:
        async with self._session(session) as s:
            stmt = select(FinalizedPriceRecord).where(
                FinalizedPriceRecord.business_date == business_date
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())


class NAVSnapshotRepository(BaseRepository):
    """Data access for NAV snapshots."""

    async def upsert(
        self,
        *,
        portfolio_id: str,
        business_date: date,
        gross_market_value: Any,
        net_market_value: Any,
        cash_balance: Any,
        accrued_fees: Any,
        nav: Any,
        nav_per_share: Any,
        shares_outstanding: Any,
        currency: str,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(NAVSnapshotRecord).values(
                portfolio_id=portfolio_id,
                business_date=business_date,
                gross_market_value=gross_market_value,
                net_market_value=net_market_value,
                cash_balance=cash_balance,
                accrued_fees=accrued_fees,
                nav=nav,
                nav_per_share=nav_per_share,
                shares_outstanding=shares_outstanding,
                currency=currency,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=NAVSnapshotRecord.__table__.primary_key,
                set_={
                    "nav": stmt.excluded.nav,
                    "net_market_value": stmt.excluded.net_market_value,
                    "gross_market_value": stmt.excluded.gross_market_value,
                    "cash_balance": stmt.excluded.cash_balance,
                    "accrued_fees": stmt.excluded.accrued_fees,
                    "nav_per_share": stmt.excluded.nav_per_share,
                    "shares_outstanding": stmt.excluded.shares_outstanding,
                },
            )
            await s.execute(stmt)
            await s.commit()


class PnLSnapshotRepository(BaseRepository):
    """Data access for frozen daily P&L."""

    async def upsert(
        self,
        *,
        portfolio_id: str,
        business_date: date,
        total_realized_pnl: Any,
        total_unrealized_pnl: Any,
        total_pnl: Any,
        position_count: int,
        details: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(PnLSnapshotRecord).values(
                portfolio_id=portfolio_id,
                business_date=business_date,
                total_realized_pnl=total_realized_pnl,
                total_unrealized_pnl=total_unrealized_pnl,
                total_pnl=total_pnl,
                position_count=position_count,
                details=details,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=PnLSnapshotRecord.__table__.primary_key,
                set_={
                    "total_realized_pnl": stmt.excluded.total_realized_pnl,
                    "total_unrealized_pnl": stmt.excluded.total_unrealized_pnl,
                    "total_pnl": stmt.excluded.total_pnl,
                    "position_count": stmt.excluded.position_count,
                    "details": stmt.excluded.details,
                },
            )
            await s.execute(stmt)
            await s.commit()


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
                constraint=ReconciliationRecord.__table__.primary_key,
                set_={
                    "total_positions": stmt.excluded.total_positions,
                    "matched_positions": stmt.excluded.matched_positions,
                    "is_clean": stmt.excluded.is_clean,
                    "breaks": stmt.excluded.breaks,
                },
            )
            await s.execute(stmt)
            await s.commit()
