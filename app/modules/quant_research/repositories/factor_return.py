"""Factor return persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.quant_research.models.factor_return import FactorReturnRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FactorReturnRepository(BaseRepository):
    """CRUD for FactorReturnRecord."""

    async def insert_batch(
        self, records: list[FactorReturnRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            for r in records:
                s.add(r)
            await s.commit()

    async def get_by_factor(
        self,
        factor_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[FactorReturnRecord]:
        async with self._session(session) as s:
            stmt = select(FactorReturnRecord).where(FactorReturnRecord.factor_id == factor_id)
            if start_date is not None:
                stmt = stmt.where(FactorReturnRecord.return_date >= start_date)
            if end_date is not None:
                stmt = stmt.where(FactorReturnRecord.return_date <= end_date)
            stmt = stmt.order_by(FactorReturnRecord.return_date)
            result = await s.execute(stmt)
            return list(result.scalars().all())
