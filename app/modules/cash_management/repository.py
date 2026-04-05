"""Cash management data persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.cash_management.models import (
    CashBalanceRecord,
    CashJournalRecord,
    CashProjectionRecord,
    CashSettlementRecord,
    ScheduledFlowRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CashBalanceRepository(BaseRepository):
    async def get_by_portfolio(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[CashBalanceRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashBalanceRecord).where(CashBalanceRecord.portfolio_id == str(portfolio_id))
            )
            return list(result.scalars().all())

    async def get_by_portfolio_currency(
        self, portfolio_id: UUID, currency: str, *, session: AsyncSession | None = None
    ) -> CashBalanceRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashBalanceRecord).where(
                    CashBalanceRecord.portfolio_id == str(portfolio_id),
                    CashBalanceRecord.currency == currency,
                )
            )
            return result.scalar_one_or_none()

    async def upsert(
        self, record: CashBalanceRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            existing = await session.execute(
                select(CashBalanceRecord).where(
                    CashBalanceRecord.portfolio_id == record.portfolio_id,
                    CashBalanceRecord.currency == record.currency,
                )
            )
            row = existing.scalar_one_or_none()
            if row:
                await session.execute(
                    update(CashBalanceRecord)
                    .where(CashBalanceRecord.id == row.id)
                    .values(
                        available_balance=record.available_balance,
                        pending_inflows=record.pending_inflows,
                        pending_outflows=record.pending_outflows,
                    )
                )
            else:
                session.add(record)
            await session.commit()


class CashJournalRepository(BaseRepository):
    async def insert(
        self, record: CashJournalRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        limit: int = 100,
        *,
        session: AsyncSession | None = None,
    ) -> list[CashJournalRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashJournalRecord)
                .where(CashJournalRecord.portfolio_id == str(portfolio_id))
                .order_by(CashJournalRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())


class SettlementRepository(BaseRepository):
    async def insert(
        self, record: CashSettlementRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_pending(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[CashSettlementRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashSettlementRecord)
                .where(
                    CashSettlementRecord.portfolio_id == str(portfolio_id),
                    CashSettlementRecord.status == "pending",
                )
                .order_by(CashSettlementRecord.settlement_date.asc())
            )
            return list(result.scalars().all())

    async def get_by_date_range(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[CashSettlementRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashSettlementRecord)
                .where(
                    CashSettlementRecord.portfolio_id == str(portfolio_id),
                    CashSettlementRecord.settlement_date >= start,
                    CashSettlementRecord.settlement_date <= end,
                )
                .order_by(CashSettlementRecord.settlement_date.asc())
            )
            return list(result.scalars().all())

    async def settle(self, settlement_id: str, *, session: AsyncSession | None = None) -> None:
        """Mark a settlement as settled."""
        async with self._session(session) as session:
            await session.execute(
                update(CashSettlementRecord)
                .where(CashSettlementRecord.id == settlement_id)
                .values(status="settled")
            )
            await session.commit()

    async def get_due_settlements(
        self, as_of: date, *, session: AsyncSession | None = None
    ) -> list[CashSettlementRecord]:
        """Get all pending settlements due on or before a date."""
        async with self._session(session) as session:
            result = await session.execute(
                select(CashSettlementRecord)
                .where(
                    CashSettlementRecord.status == "pending",
                    CashSettlementRecord.settlement_date <= as_of,
                )
                .order_by(CashSettlementRecord.settlement_date.asc())
            )
            return list(result.scalars().all())


class ScheduledFlowRepository(BaseRepository):
    async def insert(
        self, record: ScheduledFlowRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[ScheduledFlowRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(ScheduledFlowRecord)
                .where(
                    ScheduledFlowRecord.portfolio_id == str(portfolio_id),
                    ScheduledFlowRecord.flow_date >= start,
                    ScheduledFlowRecord.flow_date <= end,
                )
                .order_by(ScheduledFlowRecord.flow_date.asc())
            )
            return list(result.scalars().all())


class CashProjectionRepository(BaseRepository):
    async def save(
        self, record: CashProjectionRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_latest(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> CashProjectionRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashProjectionRecord)
                .where(CashProjectionRecord.portfolio_id == str(portfolio_id))
                .order_by(CashProjectionRecord.projected_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
