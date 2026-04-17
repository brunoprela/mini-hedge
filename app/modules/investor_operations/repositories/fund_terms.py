"""FundTermsRepository — CRUD for positions.fund_terms."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import select

from app.modules.investor_operations.models.fund_terms import FundTermsRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FundTermsRepository(BaseRepository):
    """CRUD for positions.fund_terms."""

    async def get_by_share_class(
        self, share_class: str, *, session: AsyncSession | None = None
    ) -> FundTermsRecord | None:
        async with self._session(session) as s:
            stmt = select(FundTermsRecord).where(FundTermsRecord.share_class == share_class)
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def list_active(self, *, session: AsyncSession | None = None) -> list[FundTermsRecord]:
        async with self._session(session) as s:
            stmt = (
                select(FundTermsRecord)
                .where(FundTermsRecord.is_active.is_(True))
                .order_by(FundTermsRecord.share_class)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def upsert(self, record: FundTermsRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as s:
            # Avoid session.merge() — it issues implicit SELECTs that can
            # hang with PgBouncer transaction-mode pooling.  The service
            # layer already distinguishes insert vs update, so add() is
            # sufficient for new records and a no-op for already-tracked ones.
            inspected = sa.inspect(record, raiseerr=False)
            if inspected is None or inspected.transient:
                s.add(record)
            await s.flush()
