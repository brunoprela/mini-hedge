"""FX forward contract persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.fx_hedging.models.fx_forward import FXForwardRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import AsyncSession


class FXForwardRepository(BaseRepository):
    """CRUD for FX forward contracts."""

    async def insert(
        self,
        record: FXForwardRecord,
        *,
        session: AsyncSession | None = None,
    ) -> FXForwardRecord:
        async with self._session(session) as s:
            s.add(record)
            await s.flush()
            await s.commit()
            return record

    async def get_by_id(
        self,
        forward_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> FXForwardRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FXForwardRecord).where(FXForwardRecord.id == str(forward_id))
            )
            return result.scalar_one_or_none()

    async def get_open_by_portfolio(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[FXForwardRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(FXForwardRecord)
                .where(
                    FXForwardRecord.portfolio_id == str(portfolio_id),
                    FXForwardRecord.status == "open",
                )
                .order_by(FXForwardRecord.maturity_date.asc())
            )
            return list(result.scalars().all())

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        *,
        status: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[FXForwardRecord]:
        async with self._session(session) as s:
            stmt = select(FXForwardRecord).where(
                FXForwardRecord.portfolio_id == str(portfolio_id),
            )
            if status is not None:
                stmt = stmt.where(FXForwardRecord.status == status)
            stmt = stmt.order_by(FXForwardRecord.maturity_date.asc())
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def get_expiring(
        self,
        cutoff_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[FXForwardRecord]:
        """Get all open forwards maturing on or before cutoff_date."""
        async with self._session(session) as s:
            result = await s.execute(
                select(FXForwardRecord)
                .where(
                    FXForwardRecord.status == "open",
                    FXForwardRecord.maturity_date <= cutoff_date,
                )
                .order_by(FXForwardRecord.maturity_date.asc())
            )
            return list(result.scalars().all())

    async def update_status(
        self,
        forward_id: UUID,
        status: str,
        *,
        close_rate: Decimal | None = None,
        close_spot: Decimal | None = None,
        closed_at: datetime | None = None,
        realized_pnl: Decimal | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            values: dict[str, object] = {"status": status}
            if close_rate is not None:
                values["close_rate"] = close_rate
            if close_spot is not None:
                values["close_spot"] = close_spot
            if closed_at is not None:
                values["closed_at"] = closed_at
            if realized_pnl is not None:
                values["realized_pnl"] = realized_pnl
            await s.execute(
                update(FXForwardRecord)
                .where(FXForwardRecord.id == str(forward_id))
                .values(**values)
            )
            await s.commit()

    async def update_mtm(
        self,
        forward_id: UUID,
        mtm_value: Decimal,
        mtm_timestamp: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            await s.execute(
                update(FXForwardRecord)
                .where(FXForwardRecord.id == str(forward_id))
                .values(mtm_value=mtm_value, mtm_timestamp=mtm_timestamp)
            )
            await s.commit()
