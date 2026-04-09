"""Fund of funds repository."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.modules.fund_structures.models.fund_of_funds_holding import FundOfFundsHoldingRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FundOfFundsRepository(BaseRepository):
    async def add_holding(
        self,
        record: FundOfFundsHoldingRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def list_holdings(
        self,
        fof_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[FundOfFundsHoldingRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(FundOfFundsHoldingRecord)
                .where(
                    FundOfFundsHoldingRecord.fof_fund_slug == fof_slug,
                    FundOfFundsHoldingRecord.is_active.is_(True),
                )
                .order_by(FundOfFundsHoldingRecord.created_at)
            )
            return list(result.scalars().all())

    async def update_nav(
        self,
        holding_id: str,
        nav: Decimal,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            await s.execute(
                update(FundOfFundsHoldingRecord)
                .where(FundOfFundsHoldingRecord.id == holding_id)
                .values(current_nav=nav, updated_at=datetime.now(UTC))
            )
            await s.commit()

    async def remove_holding(
        self,
        holding_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Soft-delete by deactivating."""
        async with self._session(session) as s:
            await s.execute(
                update(FundOfFundsHoldingRecord)
                .where(FundOfFundsHoldingRecord.id == holding_id)
                .values(is_active=False, updated_at=datetime.now(UTC))
            )
            await s.commit()
