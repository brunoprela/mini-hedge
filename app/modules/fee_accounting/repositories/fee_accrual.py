"""Fee accrual repository."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.fee_accounting.models.fee_accrual import FeeAccrualRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FeeAccrualRepository(BaseRepository):
    """CRUD for fee accruals."""

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        start: date | None = None,
        end: date | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[FeeAccrualRecord]:
        async with self._session(session) as session:
            stmt = select(FeeAccrualRecord).where(
                FeeAccrualRecord.portfolio_id == str(portfolio_id)
            )
            if start is not None:
                stmt = stmt.where(FeeAccrualRecord.accrual_date >= start)
            if end is not None:
                stmt = stmt.where(FeeAccrualRecord.accrual_date <= end)
            stmt = stmt.order_by(FeeAccrualRecord.accrual_date.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_by_type(
        self,
        portfolio_id: UUID,
        fee_type: str,
        *,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> FeeAccrualRecord | None:
        async with self._session(session) as session:
            stmt = (
                select(FeeAccrualRecord)
                .where(
                    FeeAccrualRecord.portfolio_id == str(portfolio_id),
                    FeeAccrualRecord.fee_type == fee_type,
                    FeeAccrualRecord.share_class == share_class,
                )
                .order_by(FeeAccrualRecord.accrual_date.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(
        self, record: FeeAccrualRecord, *, session: AsyncSession | None = None
    ) -> FeeAccrualRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def update_status(
        self,
        accrual_id: UUID,
        status: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            stmt = (
                update(FeeAccrualRecord)
                .where(FeeAccrualRecord.id == str(accrual_id))
                .values(status=status)
            )
            await session.execute(stmt)
            await session.commit()
