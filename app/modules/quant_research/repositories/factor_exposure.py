"""Factor exposure persistence (quant_research module)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.quant_research.models.factor_exposure import FactorExposureRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FactorExposureRepository(BaseRepository):
    """CRUD for quant_research FactorExposureRecord."""

    async def save_many(
        self, records: list[FactorExposureRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            for r in records:
                s.add(r)
            await s.commit()

    async def get_by_factor_date(
        self,
        factor_id: str,
        as_of_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[FactorExposureRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(FactorExposureRecord)
                .where(
                    FactorExposureRecord.factor_id == factor_id,
                    FactorExposureRecord.as_of_date == as_of_date,
                )
                .order_by(FactorExposureRecord.exposure.desc())
            )
            return list(result.scalars().all())
