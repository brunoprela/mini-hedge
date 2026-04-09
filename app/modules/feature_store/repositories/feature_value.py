"""Feature value persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.modules.feature_store.models.feature_value import FeatureValueRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FeatureValueRepository(BaseRepository):
    """CRUD for FeatureValueRecord."""

    async def save_many(
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
