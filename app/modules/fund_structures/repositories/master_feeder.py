"""Master-feeder link repository."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.modules.fund_structures.models.master_feeder_link import MasterFeederLinkRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
