"""Factor definition persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.quant_research.models.factor_definition import FactorDefinitionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FactorDefinitionRepository(BaseRepository):
    """CRUD for FactorDefinitionRecord."""

    async def create(
        self, record: FactorDefinitionRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_by_id(
        self, factor_id: str, *, session: AsyncSession | None = None
    ) -> FactorDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FactorDefinitionRecord).where(FactorDefinitionRecord.id == factor_id)
            )
            return result.scalar_one_or_none()

    async def get_by_name(
        self, name: str, *, session: AsyncSession | None = None
    ) -> FactorDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FactorDefinitionRecord).where(FactorDefinitionRecord.name == name)
            )
            return result.scalar_one_or_none()

    async def list_all(
        self, *, active_only: bool = True, session: AsyncSession | None = None
    ) -> list[FactorDefinitionRecord]:
        async with self._session(session) as s:
            stmt = select(FactorDefinitionRecord)
            if active_only:
                stmt = stmt.where(FactorDefinitionRecord.is_active.is_(True))
            stmt = stmt.order_by(FactorDefinitionRecord.name)
            result = await s.execute(stmt)
            return list(result.scalars().all())
