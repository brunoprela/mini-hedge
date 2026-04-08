"""Fund structures data persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.modules.fund_structures.models import (
    FundOfFundsHoldingRecord,
    MasterFeederLinkRecord,
    StrategyBookRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Master-Feeder
# ---------------------------------------------------------------------------


class MasterFeederRepository(BaseRepository):
    async def create_link(
        self,
        record: MasterFeederLinkRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_feeders_for_master(
        self,
        master_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[MasterFeederLinkRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(MasterFeederLinkRecord)
                .where(
                    MasterFeederLinkRecord.master_fund_slug == master_slug,
                    MasterFeederLinkRecord.is_active.is_(True),
                )
                .order_by(MasterFeederLinkRecord.created_at)
            )
            return list(result.scalars().all())

    async def get_master_for_feeder(
        self,
        feeder_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> MasterFeederLinkRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(MasterFeederLinkRecord).where(
                    MasterFeederLinkRecord.feeder_fund_slug == feeder_slug,
                    MasterFeederLinkRecord.is_active.is_(True),
                )
            )
            return result.scalar_one_or_none()

    async def update_allocation(
        self,
        link_id: str,
        pct: Decimal,
        *,
        session: AsyncSession | None = None,
    ) -> MasterFeederLinkRecord | None:
        async with self._session(session) as s:
            await s.execute(
                update(MasterFeederLinkRecord)
                .where(MasterFeederLinkRecord.id == link_id)
                .values(allocation_pct=pct)
            )
            await s.commit()
            result = await s.execute(
                select(MasterFeederLinkRecord).where(
                    MasterFeederLinkRecord.id == link_id,
                )
            )
            return result.scalar_one_or_none()

    async def deactivate(
        self,
        link_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            await s.execute(
                update(MasterFeederLinkRecord)
                .where(MasterFeederLinkRecord.id == link_id)
                .values(is_active=False)
            )
            await s.commit()


# ---------------------------------------------------------------------------
# Strategy Books
# ---------------------------------------------------------------------------


class StrategyBookRepository(BaseRepository):
    async def create(
        self,
        record: StrategyBookRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_by_id(
        self,
        book_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> StrategyBookRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(StrategyBookRecord).where(StrategyBookRecord.id == book_id)
            )
            return result.scalar_one_or_none()

    async def list_by_fund(
        self,
        fund_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[StrategyBookRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(StrategyBookRecord)
                .where(
                    StrategyBookRecord.fund_slug == fund_slug,
                    StrategyBookRecord.is_active.is_(True),
                )
                .order_by(StrategyBookRecord.created_at)
            )
            return list(result.scalars().all())

    async def get_children(
        self,
        parent_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[StrategyBookRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(StrategyBookRecord)
                .where(
                    StrategyBookRecord.parent_id == parent_id,
                    StrategyBookRecord.is_active.is_(True),
                )
                .order_by(StrategyBookRecord.name)
            )
            return list(result.scalars().all())

    async def get_tree(
        self,
        fund_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[StrategyBookRecord]:
        """Return all active books for a fund (flat list; caller builds tree)."""
        return await self.list_by_fund(fund_slug, session=session)

    async def update(
        self,
        book_id: str,
        *,
        name: str | None = None,
        target_pct: Decimal | None = None,
        session: AsyncSession | None = None,
    ) -> StrategyBookRecord | None:
        async with self._session(session) as s:
            values: dict[str, object] = {}
            if name is not None:
                values["name"] = name
            if target_pct is not None:
                values["target_allocation_pct"] = target_pct
            if values:
                await s.execute(
                    update(StrategyBookRecord)
                    .where(StrategyBookRecord.id == book_id)
                    .values(**values)
                )
                await s.commit()
            result = await s.execute(
                select(StrategyBookRecord).where(StrategyBookRecord.id == book_id)
            )
            return result.scalar_one_or_none()

    async def delete(
        self,
        book_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Soft-delete by deactivating."""
        async with self._session(session) as s:
            await s.execute(
                update(StrategyBookRecord)
                .where(StrategyBookRecord.id == book_id)
                .values(is_active=False)
            )
            await s.commit()


# ---------------------------------------------------------------------------
# Fund of Funds
# ---------------------------------------------------------------------------


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
