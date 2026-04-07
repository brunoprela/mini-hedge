"""Data access for capital accounts and transactions."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.modules.capital_accounts.models import CapitalAccountRecord, CapitalTransactionRecord
from app.modules.platform.models import InvestorRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class InvestorRepository(BaseRepository):
    """CRUD for platform.investors."""

    async def get_all_active(self, *, session: AsyncSession | None = None) -> list[InvestorRecord]:
        async with self._session(session) as session:
            stmt = (
                select(InvestorRecord)
                .where(InvestorRecord.is_active.is_(True))
                .order_by(InvestorRecord.name)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(
        self, investor_id: str, *, session: AsyncSession | None = None
    ) -> InvestorRecord | None:
        async with self._session(session) as session:
            stmt = select(InvestorRecord).where(InvestorRecord.id == investor_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(self, record: InvestorRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()

    async def insert_batch(
        self, records: list[InvestorRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add_all(records)
            await session.flush()
            await session.commit()


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
        limit: int = 90,
        session: AsyncSession | None = None,
    ) -> list[CapitalAccountRecord]:
        """Get capital account history for an investor (most recent first)."""
        async with self._session(session) as session:
            stmt = (
                select(CapitalAccountRecord)
                .where(CapitalAccountRecord.investor_id == investor_id)
                .order_by(CapitalAccountRecord.effective_date.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_for_investor(
        self,
        investor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> CapitalAccountRecord | None:
        async with self._session(session) as session:
            stmt = (
                select(CapitalAccountRecord)
                .where(CapitalAccountRecord.investor_id == investor_id)
                .order_by(CapitalAccountRecord.effective_date.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

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


class CapitalTransactionRepository(BaseRepository):
    """CRUD for fund-scoped capital_transactions."""

    async def get_by_account(
        self,
        capital_account_id: str,
        *,
        limit: int = 100,
        session: AsyncSession | None = None,
    ) -> list[CapitalTransactionRecord]:
        async with self._session(session) as session:
            stmt = (
                select(CapitalTransactionRecord)
                .where(CapitalTransactionRecord.capital_account_id == capital_account_id)
                .order_by(CapitalTransactionRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_investor(
        self,
        investor_id: str,
        *,
        limit: int = 100,
        session: AsyncSession | None = None,
    ) -> list[CapitalTransactionRecord]:
        async with self._session(session) as session:
            stmt = (
                select(CapitalTransactionRecord)
                .where(CapitalTransactionRecord.investor_id == investor_id)
                .order_by(CapitalTransactionRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert(
        self, record: CapitalTransactionRecord, *, session: AsyncSession | None = None
    ) -> CapitalTransactionRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record
