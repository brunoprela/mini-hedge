"""Feature store persistence layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from app.modules.feature_store.models import (
    FeatureDefinitionRecord,
    FeatureSetRecord,
    FeatureValueRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FeatureRepository(BaseRepository):
    """CRUD operations for feature definitions, values, and sets."""

    # ------------------------------------------------------------------
    # Definitions
    # ------------------------------------------------------------------

    async def create_definition(
        self, record: FeatureDefinitionRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_definition(
        self, feature_id: str, *, session: AsyncSession | None = None
    ) -> FeatureDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FeatureDefinitionRecord).where(
                    FeatureDefinitionRecord.id == feature_id
                )
            )
            return result.scalar_one_or_none()

    async def get_by_name(
        self, name: str, *, session: AsyncSession | None = None
    ) -> FeatureDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FeatureDefinitionRecord).where(
                    FeatureDefinitionRecord.name == name
                )
            )
            return result.scalar_one_or_none()

    async def list_definitions(
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
                # Filter records that contain all requested tags
                for tag in tags:
                    stmt = stmt.where(FeatureDefinitionRecord.tags.contains([tag]))
            stmt = stmt.order_by(FeatureDefinitionRecord.name)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def update_definition(
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
            return await self.get_definition(feature_id, session=s)

    # ------------------------------------------------------------------
    # Values
    # ------------------------------------------------------------------

    async def save_values(
        self, records: list[FeatureValueRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add_all(records)
            await s.commit()

    async def get_values(
        self,
        feature_id: str,
        entity_id: str,
        *,
        latest_only: bool = True,
        session: AsyncSession | None = None,
    ) -> list[FeatureValueRecord]:
        async with self._session(session) as s:
            stmt = select(FeatureValueRecord).where(
                FeatureValueRecord.feature_id == feature_id,
                FeatureValueRecord.entity_id == entity_id,
            )
            stmt = stmt.order_by(FeatureValueRecord.computed_at.desc())
            if latest_only:
                stmt = stmt.limit(1)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def get_feature_vector(
        self,
        entity_id: str,
        feature_ids: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, FeatureValueRecord]:
        """Return the latest value for each feature_id for a given entity."""
        async with self._session(session) as s:
            out: dict[str, FeatureValueRecord] = {}
            for fid in feature_ids:
                result = await s.execute(
                    select(FeatureValueRecord)
                    .where(
                        FeatureValueRecord.feature_id == fid,
                        FeatureValueRecord.entity_id == entity_id,
                    )
                    .order_by(FeatureValueRecord.computed_at.desc())
                    .limit(1)
                )
                rec = result.scalar_one_or_none()
                if rec is not None:
                    out[fid] = rec
            return out

    async def get_stats(
        self, feature_id: str, *, session: AsyncSession | None = None
    ) -> dict[str, Any]:
        """Return aggregated statistics for a feature."""
        async with self._session(session) as s:
            result = await s.execute(
                select(
                    func.count().label("count"),
                    func.avg(FeatureValueRecord.value_numeric).label("mean"),
                    func.stddev(FeatureValueRecord.value_numeric).label("std"),
                    func.min(FeatureValueRecord.value_numeric).label("min_val"),
                    func.max(FeatureValueRecord.value_numeric).label("max_val"),
                    func.count()
                    .filter(FeatureValueRecord.value_numeric.is_(None))
                    .label("null_count"),
                    func.max(FeatureValueRecord.computed_at).label("last_computed"),
                ).where(FeatureValueRecord.feature_id == feature_id)
            )
            row = result.one()
            return {
                "count": row.count,
                "mean": row.mean,
                "std": row.std,
                "min_val": row.min_val,
                "max_val": row.max_val,
                "null_count": row.null_count,
                "last_computed": row.last_computed,
            }

    # ------------------------------------------------------------------
    # Feature sets
    # ------------------------------------------------------------------

    async def create_feature_set(
        self, record: FeatureSetRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_feature_set(
        self, set_id: str, *, session: AsyncSession | None = None
    ) -> FeatureSetRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FeatureSetRecord).where(FeatureSetRecord.id == set_id)
            )
            return result.scalar_one_or_none()

    async def list_feature_sets(
        self, *, session: AsyncSession | None = None
    ) -> list[FeatureSetRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(FeatureSetRecord).order_by(FeatureSetRecord.name)
            )
            return list(result.scalars().all())
