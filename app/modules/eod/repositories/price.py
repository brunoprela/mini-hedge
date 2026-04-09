"""Data access for locked closing prices."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.modules.eod.models.finalized_price import FinalizedPriceRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FinalizedPriceRepository(BaseRepository):
    """Data access for locked closing prices."""

    async def upsert_price(
        self,
        *,
        instrument_id: str,
        business_date: date,
        close_price: Any,
        source: str,
        finalized_by: str,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            stmt = insert(FinalizedPriceRecord).values(
                instrument_id=instrument_id,
                business_date=business_date,
                close_price=close_price,
                source=source,
                finalized_by=finalized_by,
            )
            stmt = stmt.on_conflict_do_update(
                constraint=FinalizedPriceRecord.__table__.primary_key,  # type: ignore[arg-type]
                set_={
                    "close_price": stmt.excluded.close_price,
                    "source": stmt.excluded.source,
                },
            )
            await s.execute(stmt)
            await s.commit()

    async def get_prices(
        self, business_date: date, *, session: AsyncSession | None = None
    ) -> list[FinalizedPriceRecord]:
        async with self._session(session) as s:
            stmt = select(FinalizedPriceRecord).where(
                FinalizedPriceRecord.business_date == business_date
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())
