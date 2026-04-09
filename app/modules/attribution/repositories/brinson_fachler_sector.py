"""Brinson-Fachler sector attribution persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.attribution.models.brinson_fachler_sector import BrinsonFachlerSectorRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BrinsonFachlerSectorRepository(BaseRepository):
    """CRUD for BrinsonFachlerSectorRecord."""

    async def save_many(
        self,
        records: list[BrinsonFachlerSectorRecord],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            for r in records:
                session.add(r)
            await session.commit()

    async def get_by_bf_result(
        self, bf_result_id: str, *, session: AsyncSession | None = None
    ) -> list[BrinsonFachlerSectorRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(BrinsonFachlerSectorRecord).where(
                    BrinsonFachlerSectorRecord.bf_result_id == bf_result_id
                )
            )
            return list(result.scalars().all())
