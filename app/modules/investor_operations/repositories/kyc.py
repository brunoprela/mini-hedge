"""InvestorKYCRepository — CRUD for platform.investor_kyc."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import select

from app.modules.investor_operations.models.kyc import InvestorKYCRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class InvestorKYCRepository(BaseRepository):
    """CRUD for platform.investor_kyc."""

    async def get_by_investor(
        self, investor_id: str, *, session: AsyncSession | None = None
    ) -> InvestorKYCRecord | None:
        async with self._session(session) as s:
            stmt = select(InvestorKYCRecord).where(InvestorKYCRecord.investor_id == investor_id)
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def upsert(
        self, record: InvestorKYCRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            inspected = sa.inspect(record, raiseerr=False)
            if inspected is None or inspected.transient:
                s.add(record)
            await s.flush()
