"""Capital transaction repository."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.capital_accounts.models.capital_transaction import CapitalTransactionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 100,
        session: AsyncSession | None = None,
    ) -> list[CapitalTransactionRecord]:
        async with self._session(session) as session:
            stmt = select(CapitalTransactionRecord).where(
                CapitalTransactionRecord.investor_id == investor_id
            )
            if from_date is not None:
                stmt = stmt.where(CapitalTransactionRecord.business_date >= from_date)
            if to_date is not None:
                stmt = stmt.where(CapitalTransactionRecord.business_date <= to_date)
            stmt = stmt.order_by(CapitalTransactionRecord.created_at.desc()).limit(limit)
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
