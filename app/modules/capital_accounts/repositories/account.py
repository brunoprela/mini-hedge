"""Capital account repository."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.modules.capital_accounts.models.capital_account import CapitalAccountRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CapitalAccountRepository(BaseRepository):
    """CRUD for fund-scoped capital_accounts."""

    async def get_latest_by_fund(
        self, *, session: AsyncSession | None = None
    ) -> list[CapitalAccountRecord]:
        """Get the most recent snapshot for each investor in the fund."""
        async with self._session(session) as session:
            # Subquery: max effective_date per investor
            sub = (
                select(
                    CapitalAccountRecord.investor_id,
                    func.max(CapitalAccountRecord.effective_date).label("max_date"),
                )
                .group_by(CapitalAccountRecord.investor_id)
                .subquery()
            )
            stmt = select(CapitalAccountRecord).join(
                sub,
                (CapitalAccountRecord.investor_id == sub.c.investor_id)
                & (CapitalAccountRecord.effective_date == sub.c.max_date),
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_investor(
        self,
        investor_id: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 90,
        session: AsyncSession | None = None,
    ) -> list[CapitalAccountRecord]:
        """Get capital account history for an investor (most recent first)."""
        async with self._session(session) as session:
            stmt = (
                select(CapitalAccountRecord)
                .where(CapitalAccountRecord.investor_id == investor_id)
            )
            if from_date is not None:
                stmt = stmt.where(CapitalAccountRecord.effective_date >= from_date)
            if to_date is not None:
                stmt = stmt.where(CapitalAccountRecord.effective_date <= to_date)
            stmt = stmt.order_by(CapitalAccountRecord.effective_date.desc()).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_for_investor(
        self,
        investor_id: str,
        *,
        share_class: str | None = None,
        session: AsyncSession | None = None,
    ) -> CapitalAccountRecord | None:
        async with self._session(session) as session:
            stmt = select(CapitalAccountRecord).where(
                CapitalAccountRecord.investor_id == investor_id
            )
            if share_class is not None:
                stmt = stmt.where(CapitalAccountRecord.share_class == share_class)
            stmt = stmt.order_by(CapitalAccountRecord.effective_date.desc()).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_latest_for_investor_by_class(
        self,
        investor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[CapitalAccountRecord]:
        """Get the latest account per share class for an investor."""
        async with self._session(session) as session:
            sub = (
                select(
                    CapitalAccountRecord.share_class,
                    func.max(CapitalAccountRecord.effective_date).label("max_date"),
                )
                .where(CapitalAccountRecord.investor_id == investor_id)
                .group_by(CapitalAccountRecord.share_class)
                .subquery()
            )
            stmt = select(CapitalAccountRecord).join(
                sub,
                (CapitalAccountRecord.investor_id == investor_id)
                & (CapitalAccountRecord.share_class == sub.c.share_class)
                & (CapitalAccountRecord.effective_date == sub.c.max_date),
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_by_share_class(
        self,
        share_class: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[CapitalAccountRecord]:
        """Get latest snapshot for all investors in a specific share class."""
        async with self._session(session) as session:
            sub = (
                select(
                    CapitalAccountRecord.investor_id,
                    func.max(CapitalAccountRecord.effective_date).label("max_date"),
                )
                .where(CapitalAccountRecord.share_class == share_class)
                .group_by(CapitalAccountRecord.investor_id)
                .subquery()
            )
            stmt = (
                select(CapitalAccountRecord)
                .join(
                    sub,
                    (CapitalAccountRecord.investor_id == sub.c.investor_id)
                    & (CapitalAccountRecord.effective_date == sub.c.max_date),
                )
                .where(CapitalAccountRecord.share_class == share_class)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert(
        self, record: CapitalAccountRecord, *, session: AsyncSession | None = None
    ) -> CapitalAccountRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_total_shares(self, *, session: AsyncSession | None = None) -> Decimal:
        """Sum of shares_held across all investors (latest snapshot only)."""
        latest = await self.get_latest_by_fund(session=session)
        return Decimal(sum(a.shares_held for a in latest)) if latest else Decimal(0)
