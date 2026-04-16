"""Backtesting data persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select, update

from app.modules.backtesting.models import BacktestRunRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


class BacktestRepository(BaseRepository):
    """CRUD operations for backtest runs."""

    async def create(
        self,
        record: BacktestRunRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_by_id(
        self,
        backtest_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> BacktestRunRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(BacktestRunRecord).where(
                    BacktestRunRecord.id == backtest_id,
                )
            )
            return result.scalar_one_or_none()

    async def list_all(
        self,
        fund_slug: str,
        *,
        status: str | None = None,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[BacktestRunRecord]:
        async with self._session(session) as s:
            stmt = (
                select(BacktestRunRecord)
                .where(BacktestRunRecord.fund_slug == fund_slug)
                .order_by(BacktestRunRecord.created_at.desc())
            )
            if status is not None:
                stmt = stmt.where(BacktestRunRecord.status == status)
            stmt = stmt.limit(limit)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def update_status(
        self,
        backtest_id: str,
        status: str,
        *,
        results: dict[str, Any] | None = None,
        equity_curve: list[dict[str, Any]] | None = None,
        trades: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            values: dict[str, Any] = {"status": status}
            if results is not None:
                values["results"] = results
            if equity_curve is not None:
                values["equity_curve"] = equity_curve
            if trades is not None:
                values["trades"] = trades
            if error_message is not None:
                values["error_message"] = error_message
            if completed_at is not None:
                values["completed_at"] = completed_at
            await s.execute(
                update(BacktestRunRecord)
                .where(BacktestRunRecord.id == backtest_id)
                .values(**values)
            )
            await s.commit()

    async def delete(
        self,
        backtest_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            await s.execute(
                delete(BacktestRunRecord).where(
                    BacktestRunRecord.id == backtest_id,
                )
            )
            await s.commit()
