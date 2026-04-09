"""Cash balance persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.cash_management.models.cash_balance import CashBalanceRecord
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
