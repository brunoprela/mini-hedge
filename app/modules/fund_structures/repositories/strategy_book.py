"""Strategy book repository."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.modules.fund_structures.models.strategy_book import StrategyBookRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class StrategyBookRepository(BaseRepository):
    async def insert(
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
