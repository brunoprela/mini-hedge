"""Feature definition persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from app.modules.feature_store.models.feature_definition import FeatureDefinitionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FeatureDefinitionRepository(BaseRepository):
    """CRUD for FeatureDefinitionRecord."""

    async def insert(
        self, record: FeatureDefinitionRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_by_id(
        self, feature_id: str, *, session: AsyncSession | None = None
    ) -> FeatureDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FeatureDefinitionRecord).where(FeatureDefinitionRecord.id == feature_id)
            )
            return result.scalar_one_or_none()

    async def get_by_name(
        self, name: str, *, session: AsyncSession | None = None
    ) -> FeatureDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FeatureDefinitionRecord).where(FeatureDefinitionRecord.name == name)
            )
            return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        entity_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        session: AsyncSession | None = None,
    ) -> list[FeatureDefinitionRecord]:
        async with self._session(session) as s:
            stmt = select(FeatureDefinitionRecord)
            if entity_type is not None:
                stmt = stmt.where(FeatureDefinitionRecord.entity_type == entity_type)
            if status is not None:
                stmt = stmt.where(FeatureDefinitionRecord.status == status)
            if tags:
                for tag in tags:
                    stmt = stmt.where(FeatureDefinitionRecord.tags.contains([tag]))
            stmt = stmt.order_by(FeatureDefinitionRecord.name)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def update(
        self,
        feature_id: str,
        *,
        expression: str | None = None,
        version: int | None = None,
        status: str | None = None,
        session: AsyncSession | None = None,
    ) -> FeatureDefinitionRecord | None:
        async with self._session(session) as s:
            values: dict[str, Any] = {}
            if expression is not None:
                values["expression"] = expression
            if version is not None:
                values["version"] = version
            if status is not None:
                values["status"] = status
            if values:
                values["updated_at"] = func.now()
                await s.execute(
                    update(FeatureDefinitionRecord)
                    .where(FeatureDefinitionRecord.id == feature_id)
                    .values(**values)
                )
                await s.commit()
            return await self.get_by_id(feature_id, session=s)
