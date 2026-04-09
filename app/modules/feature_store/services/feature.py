"""Feature store service — manages feature lifecycle and computation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from app.modules.feature_store.interfaces import (
    ComputeMethod,
    FeatureDefinition,
    FeatureSet,
    FeatureStats,
    FeatureStatus,
    FeatureType,
    FeatureValue,
    FeatureVector,
)
from app.modules.feature_store.models.feature_definition import FeatureDefinitionRecord
from app.modules.feature_store.models.feature_set import FeatureSetRecord
from app.modules.feature_store.models.feature_value import FeatureValueRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import shared_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.feature_store.core.compute_engine import FeatureComputeEngine
    from app.modules.feature_store.repositories import (
        FeatureDefinitionRepository,
        FeatureSetRepository,
        FeatureValueRepository,
    )
    from app.shared.events import EventBus

logger = structlog.get_logger()


class FeatureStoreService:
    """Manages feature registration, computation, and retrieval."""

    def __init__(
        self,
        definition_repo: FeatureDefinitionRepository,
        value_repo: FeatureValueRepository,
        set_repo: FeatureSetRepository,
        compute_engine: FeatureComputeEngine,
        session_factory: Any,
        event_bus: EventBus | None = None,
    ) -> None:
        self._definition_repo = definition_repo
        self._value_repo = value_repo
        self._set_repo = set_repo
        self._compute_engine = compute_engine
        self._session_factory = session_factory
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Feature definitions
    # ------------------------------------------------------------------

    async def register_feature(
        self,
        name: str,
        description: str,
        feature_type: FeatureType,
        compute_method: ComputeMethod,
        expression: str,
        entity_type: str,
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> FeatureDefinition:
        now = datetime.now(UTC)
        record = FeatureDefinitionRecord(
            name=name,
            description=description,
            feature_type=feature_type.value,
            compute_method=compute_method.value,
            expression=expression,
            dependencies=dependencies or [],
            entity_type=entity_type,
            version=1,
            status=FeatureStatus.ACTIVE.value,
            tags=tags or [],
            created_at=now,
            updated_at=now,
        )
        await self._definition_repo.create(record, session=session)
        logger.info("feature_registered", name=name, entity_type=entity_type)

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.FEATURE_REGISTERED,
                    data={
                        "feature_id": record.id,
                        "name": name,
                        "feature_type": feature_type.value,
                        "compute_method": compute_method.value,
                        "entity_type": entity_type,
                    },
                ),
            )

        return self._def_to_dto(record)

    async def list_features(
        self,
        *,
        entity_type: str | None = None,
        status: FeatureStatus | None = None,
        session: AsyncSession | None = None,
    ) -> list[FeatureDefinition]:
        status_val = status.value if status is not None else None
        records = await self._definition_repo.list_all(
            entity_type=entity_type,
            status=status_val,
            session=session,
        )
        return [self._def_to_dto(r) for r in records]

    async def deprecate_feature(
        self,
        feature_name: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        record = await self._definition_repo.get_by_name(feature_name, session=session)
        if record is None:
            msg = f"Feature '{feature_name}' not found"
            raise ValueError(msg)
        await self._definition_repo.update(
            record.id,
            status=FeatureStatus.DEPRECATED.value,
            session=session,
        )
        logger.info("feature_deprecated", name=feature_name)

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    async def compute_feature(
        self,
        feature_name: str,
        entity_id: str,
        data: dict[str, Any],
        *,
        session: AsyncSession | None = None,
    ) -> FeatureValue:
        record = await self._definition_repo.get_by_name(feature_name, session=session)
        if record is None:
            msg = f"Feature '{feature_name}' not found"
            raise ValueError(msg)

        defn = self._def_to_dto(record)
        result = self._compute_engine.compute(defn, data)
        now = datetime.now(UTC)

        is_numeric = isinstance(result, (int, float, Decimal))
        is_complex = isinstance(result, (dict, list))
        val_record = FeatureValueRecord(
            feature_id=record.id,
            entity_id=entity_id,
            value_numeric=(Decimal(str(result)) if is_numeric else None),
            value_text=(
                str(result) if result is not None and not is_numeric and not is_complex else None
            ),
            value_json=result if is_complex else None,
            computed_at=now,
            version=record.version,
        )
        await self._value_repo.save_many([val_record], session=session)

        return FeatureValue(
            feature_name=feature_name,
            entity_id=entity_id,
            value=result,
            computed_at=now,
            version=record.version,
        )

    async def compute_features_batch(
        self,
        feature_names: list[str],
        entities_data: dict[str, dict[str, Any]],
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, FeatureVector]:
        definitions: list[FeatureDefinition] = []
        def_records: dict[str, FeatureDefinitionRecord] = {}
        for name in feature_names:
            rec = await self._definition_repo.get_by_name(name, session=session)
            if rec is None:
                msg = f"Feature '{name}' not found"
                raise ValueError(msg)
            definitions.append(self._def_to_dto(rec))
            def_records[name] = rec

        batch_results = self._compute_engine.compute_batch(definitions, entities_data)
        now = datetime.now(UTC)
        val_records: list[FeatureValueRecord] = []

        vectors: dict[str, FeatureVector] = {}
        for entity_id, features in batch_results.items():
            for feat_name, value in features.items():
                rec = def_records[feat_name]
                is_num = isinstance(value, (int, float, Decimal))
                is_cplx = isinstance(value, (dict, list))
                val_records.append(
                    FeatureValueRecord(
                        feature_id=rec.id,
                        entity_id=entity_id,
                        value_numeric=(Decimal(str(value)) if is_num else None),
                        value_text=(
                            str(value) if value is not None and not is_num and not is_cplx else None
                        ),
                        value_json=(value if is_cplx else None),
                        computed_at=now,
                        version=rec.version,
                    )
                )
            vectors[entity_id] = FeatureVector(
                entity_id=entity_id,
                features=features,
                computed_at=now,
            )

        if val_records:
            await self._value_repo.save_many(val_records, session=session)

        logger.info(
            "features_batch_computed",
            features=len(feature_names),
            entities=len(entities_data),
        )

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.FEATURE_COMPUTED,
                    data={
                        "feature_names": feature_names,
                        "entity_count": len(entities_data),
                        "values_computed": len(val_records),
                    },
                ),
            )

        return vectors

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def get_feature_vector(
        self,
        entity_id: str,
        feature_names: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> FeatureVector:
        feature_ids: list[str] = []
        name_map: dict[str, str] = {}  # feature_id -> name
        for name in feature_names:
            rec = await self._definition_repo.get_by_name(name, session=session)
            if rec is not None:
                feature_ids.append(rec.id)
                name_map[rec.id] = name

        raw = await self._value_repo.get_feature_vector(entity_id, feature_ids, session=session)

        features: dict[str, Any] = {}
        latest_at = datetime.now(UTC)
        for fid, val_rec in raw.items():
            fname = name_map.get(fid, fid)
            if val_rec.value_numeric is not None:
                features[fname] = val_rec.value_numeric
            elif val_rec.value_json is not None:
                features[fname] = val_rec.value_json
            elif val_rec.value_text is not None:
                features[fname] = val_rec.value_text
            latest_at = val_rec.computed_at

        return FeatureVector(
            entity_id=entity_id,
            features=features,
            computed_at=latest_at,
        )

    async def get_feature_stats(
        self,
        feature_name: str,
        *,
        session: AsyncSession | None = None,
    ) -> FeatureStats:
        rec = await self._definition_repo.get_by_name(feature_name, session=session)
        if rec is None:
            msg = f"Feature '{feature_name}' not found"
            raise ValueError(msg)

        stats = await self._value_repo.get_stats(rec.id, session=session)
        return FeatureStats(
            feature_name=feature_name,
            count=stats["count"],
            mean=Decimal(str(stats["mean"])) if stats["mean"] is not None else None,
            std=Decimal(str(stats["std"])) if stats["std"] is not None else None,
            min_val=Decimal(str(stats["min_val"])) if stats["min_val"] is not None else None,
            max_val=Decimal(str(stats["max_val"])) if stats["max_val"] is not None else None,
            null_count=stats["null_count"],
            last_computed=stats["last_computed"],
        )

    # ------------------------------------------------------------------
    # Feature sets
    # ------------------------------------------------------------------

    async def create_feature_set(
        self,
        name: str,
        description: str,
        feature_names: list[str],
        entity_type: str,
        *,
        session: AsyncSession | None = None,
    ) -> FeatureSet:
        record = FeatureSetRecord(
            name=name,
            description=description,
            feature_names=feature_names,
            entity_type=entity_type,
        )
        await self._set_repo.create(record, session=session)
        logger.info("feature_set_created", name=name)
        return self._set_to_dto(record)

    async def list_feature_sets(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[FeatureSet]:
        records = await self._set_repo.list_all(session=session)
        return [self._set_to_dto(r) for r in records]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _def_to_dto(record: FeatureDefinitionRecord) -> FeatureDefinition:
        return FeatureDefinition(
            id=UUID(record.id),
            name=record.name,
            description=record.description or "",
            feature_type=FeatureType(record.feature_type),
            compute_method=ComputeMethod(record.compute_method),
            expression=record.expression,
            dependencies=record.dependencies or [],
            entity_type=record.entity_type,
            version=record.version,
            status=FeatureStatus(record.status),
            tags=record.tags or [],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _set_to_dto(record: FeatureSetRecord) -> FeatureSet:
        return FeatureSet(
            id=UUID(record.id),
            name=record.name,
            description=record.description or "",
            feature_names=record.feature_names or [],
            entity_type=record.entity_type,
            created_at=record.created_at,
        )
