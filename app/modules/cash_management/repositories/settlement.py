"""SettlementRepository — trade settlement data access."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.cash_management.models.cash_settlement import CashSettlementRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
