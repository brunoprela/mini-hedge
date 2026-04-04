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

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory


class CashBalanceRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def get_by_portfolio(self, portfolio_id: UUID) -> list[CashBalanceRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(CashBalanceRecord).where(CashBalanceRecord.portfolio_id == str(portfolio_id))
            )
            return list(result.scalars().all())

    async def get_by_portfolio_currency(
        self, portfolio_id: UUID, currency: str
    ) -> CashBalanceRecord | None:
        async with self._sf() as session:
            result = await session.execute(
                select(CashBalanceRecord).where(
                    CashBalanceRecord.portfolio_id == str(portfolio_id),
                    CashBalanceRecord.currency == currency,
                )
            )
            return result.scalar_one_or_none()

    async def upsert(self, record: CashBalanceRecord) -> None:
        async with self._sf() as session:
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


class CashJournalRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def insert(self, record: CashJournalRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        limit: int = 100,
    ) -> list[CashJournalRecord]:
        async with self._sf() as session:
            result = await session.execute(
                select(CashJournalRecord)
                .where(CashJournalRecord.portfolio_id == str(portfolio_id))
                .order_by(CashJournalRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())


class SettlementRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def insert(self, record: CashSettlementRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_pending(self, portfolio_id: UUID) -> list[CashSettlementRecord]:
        async with self._sf() as session:
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
    ) -> list[CashSettlementRecord]:
        async with self._sf() as session:
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

    async def settle(self, settlement_id: str) -> None:
        """Mark a settlement as settled."""
        async with self._sf() as session:
            await session.execute(
                update(CashSettlementRecord)
                .where(CashSettlementRecord.id == settlement_id)
                .values(status="settled")
            )
            await session.commit()

    async def get_due_settlements(self, as_of: date) -> list[CashSettlementRecord]:
        """Get all pending settlements due on or before a date."""
        async with self._sf() as session:
            result = await session.execute(
                select(CashSettlementRecord)
                .where(
                    CashSettlementRecord.status == "pending",
                    CashSettlementRecord.settlement_date <= as_of,
                )
                .order_by(CashSettlementRecord.settlement_date.asc())
            )
            return list(result.scalars().all())


class ScheduledFlowRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def insert(self, record: ScheduledFlowRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
    ) -> list[ScheduledFlowRecord]:
        async with self._sf() as session:
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


class CashProjectionRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def save(self, record: CashProjectionRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()

    async def get_latest(self, portfolio_id: UUID) -> CashProjectionRecord | None:
        async with self._sf() as session:
            result = await session.execute(
                select(CashProjectionRecord)
                .where(CashProjectionRecord.portfolio_id == str(portfolio_id))
                .order_by(CashProjectionRecord.projected_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
