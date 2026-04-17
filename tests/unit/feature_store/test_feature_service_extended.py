"""Extended unit tests for FeatureStoreService — covering uncovered methods."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.feature_store.interfaces import (
    ComputeMethod,
    FeatureStatus,
    FeatureType,
)
from app.modules.feature_store.models.feature_definition import FeatureDefinitionRecord
from app.modules.feature_store.models.feature_set import FeatureSetRecord
from app.modules.feature_store.services import FeatureStoreService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)


def _make_def_record(name: str = "test_feature", **overrides) -> MagicMock:
    defaults = dict(
        id=str(uuid4()),
        name=name,
        description="A test feature",
        feature_type=FeatureType.NUMERIC.value,
        compute_method=ComputeMethod.PYTHON.value,
        expression="sma(prices, 5)",
        dependencies=[],
        entity_type="instrument",
        version=1,
        status=FeatureStatus.ACTIVE.value,
        tags=[],
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    record = MagicMock(spec=FeatureDefinitionRecord)
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _make_set_record(name: str = "test_set", **overrides) -> MagicMock:
    defaults = dict(
        id=str(uuid4()),
        name=name,
        description="A test feature set",
        feature_names=["sma_5", "rsi_14"],
        entity_type="instrument",
        created_at=NOW,
    )
    defaults.update(overrides)
    record = MagicMock(spec=FeatureSetRecord)
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _make_service(
    definition_repo=None,
    value_repo=None,
    set_repo=None,
    compute_engine=None,
    event_bus=None,
) -> FeatureStoreService:
    return FeatureStoreService(
        definition_repo=definition_repo or AsyncMock(),
        value_repo=value_repo or AsyncMock(),
        set_repo=set_repo or AsyncMock(),
        compute_engine=compute_engine or MagicMock(),
        session_factory=MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# deprecate_feature
# ---------------------------------------------------------------------------


class TestDeprecateFeature:
    async def test_deprecate_existing_feature(self):
        definition_repo = AsyncMock()
        record = _make_def_record("my_feature")
        definition_repo.get_by_name.return_value = record

        svc = _make_service(definition_repo=definition_repo)
        await svc.deprecate_feature("my_feature")

        definition_repo.update.assert_called_once_with(
            record.id,
            status=FeatureStatus.DEPRECATED.value,
            session=None,
        )

    async def test_deprecate_nonexistent_feature_raises(self):
        definition_repo = AsyncMock()
        definition_repo.get_by_name.return_value = None

        svc = _make_service(definition_repo=definition_repo)
        with pytest.raises(ValueError, match="not found"):
            await svc.deprecate_feature("ghost")


# ---------------------------------------------------------------------------
# compute_features_batch — not-found branch
# ---------------------------------------------------------------------------


class TestComputeFeaturesBatchNotFound:
    async def test_raises_when_feature_not_found(self):
        definition_repo = AsyncMock()
        definition_repo.get_by_name.return_value = None

        svc = _make_service(definition_repo=definition_repo)
        with pytest.raises(ValueError, match="not found"):
            await svc.compute_features_batch(
                feature_names=["missing_feat"],
                entities_data={"entity1": {"x": 1}},
            )


# ---------------------------------------------------------------------------
# get_feature_vector
# ---------------------------------------------------------------------------


class TestGetFeatureVector:
    async def test_returns_numeric_values(self):
        definition_repo = AsyncMock()
        value_repo = AsyncMock()

        feat_id = str(uuid4())
        rec = _make_def_record("sma_5", id=feat_id)
        definition_repo.get_by_name.return_value = rec

        val_rec = MagicMock()
        val_rec.value_numeric = Decimal("102.5")
        val_rec.value_json = None
        val_rec.value_text = None
        val_rec.computed_at = NOW

        value_repo.get_feature_vector.return_value = {feat_id: val_rec}

        svc = _make_service(definition_repo=definition_repo, value_repo=value_repo)
        vector = await svc.get_feature_vector("AAPL", ["sma_5"])

        assert vector.entity_id == "AAPL"
        assert vector.features["sma_5"] == Decimal("102.5")

    async def test_returns_json_values(self):
        definition_repo = AsyncMock()
        value_repo = AsyncMock()

        feat_id = str(uuid4())
        rec = _make_def_record("config_feat", id=feat_id)
        definition_repo.get_by_name.return_value = rec

        val_rec = MagicMock()
        val_rec.value_numeric = None
        val_rec.value_json = {"key": "value"}
        val_rec.value_text = None
        val_rec.computed_at = NOW

        value_repo.get_feature_vector.return_value = {feat_id: val_rec}

        svc = _make_service(definition_repo=definition_repo, value_repo=value_repo)
        vector = await svc.get_feature_vector("AAPL", ["config_feat"])

        assert vector.features["config_feat"] == {"key": "value"}

    async def test_returns_text_values(self):
        definition_repo = AsyncMock()
        value_repo = AsyncMock()

        feat_id = str(uuid4())
        rec = _make_def_record("label_feat", id=feat_id)
        definition_repo.get_by_name.return_value = rec

        val_rec = MagicMock()
        val_rec.value_numeric = None
        val_rec.value_json = None
        val_rec.value_text = "high_risk"
        val_rec.computed_at = NOW

        value_repo.get_feature_vector.return_value = {feat_id: val_rec}

        svc = _make_service(definition_repo=definition_repo, value_repo=value_repo)
        vector = await svc.get_feature_vector("AAPL", ["label_feat"])

        assert vector.features["label_feat"] == "high_risk"

    async def test_skips_unknown_features(self):
        definition_repo = AsyncMock()
        value_repo = AsyncMock()

        definition_repo.get_by_name.return_value = None
        value_repo.get_feature_vector.return_value = {}

        svc = _make_service(definition_repo=definition_repo, value_repo=value_repo)
        vector = await svc.get_feature_vector("AAPL", ["nonexistent"])

        assert vector.entity_id == "AAPL"
        assert vector.features == {}


# ---------------------------------------------------------------------------
# get_feature_stats
# ---------------------------------------------------------------------------


class TestGetFeatureStats:
    async def test_returns_stats(self):
        definition_repo = AsyncMock()
        value_repo = AsyncMock()

        rec = _make_def_record("sma_5")
        definition_repo.get_by_name.return_value = rec

        value_repo.get_stats.return_value = {
            "count": 100,
            "mean": 50.5,
            "std": 10.2,
            "min_val": 20.0,
            "max_val": 80.0,
            "null_count": 3,
            "last_computed": NOW,
        }

        svc = _make_service(definition_repo=definition_repo, value_repo=value_repo)
        stats = await svc.get_feature_stats("sma_5")

        assert stats.feature_name == "sma_5"
        assert stats.count == 100
        assert stats.mean == Decimal("50.5")
        assert stats.std == Decimal("10.2")
        assert stats.min_val == Decimal("20.0")
        assert stats.max_val == Decimal("80.0")
        assert stats.null_count == 3
        assert stats.last_computed == NOW

    async def test_returns_stats_with_none_values(self):
        definition_repo = AsyncMock()
        value_repo = AsyncMock()

        rec = _make_def_record("text_feat")
        definition_repo.get_by_name.return_value = rec

        value_repo.get_stats.return_value = {
            "count": 5,
            "mean": None,
            "std": None,
            "min_val": None,
            "max_val": None,
            "null_count": 5,
            "last_computed": None,
        }

        svc = _make_service(definition_repo=definition_repo, value_repo=value_repo)
        stats = await svc.get_feature_stats("text_feat")

        assert stats.mean is None
        assert stats.std is None
        assert stats.min_val is None
        assert stats.max_val is None

    async def test_not_found_raises(self):
        definition_repo = AsyncMock()
        definition_repo.get_by_name.return_value = None

        svc = _make_service(definition_repo=definition_repo)
        with pytest.raises(ValueError, match="not found"):
            await svc.get_feature_stats("ghost")


# ---------------------------------------------------------------------------
# create_feature_set
# ---------------------------------------------------------------------------


class TestCreateFeatureSet:
    async def test_creates_and_returns_dto(self):
        set_repo = AsyncMock()

        # Simulate DB setting server_default fields on create
        async def _seed_set(record, **kw):
            record.id = str(uuid4())
            record.created_at = NOW

        set_repo.insert.side_effect = _seed_set

        svc = _make_service(set_repo=set_repo)
        result = await svc.create_feature_set(
            name="momentum_set",
            description="Momentum features",
            feature_names=["sma_5", "rsi_14"],
            entity_type="instrument",
        )

        assert result.name == "momentum_set"
        assert result.feature_names == ["sma_5", "rsi_14"]
        assert result.entity_type == "instrument"
        set_repo.insert.assert_called_once()


# ---------------------------------------------------------------------------
# list_feature_sets
# ---------------------------------------------------------------------------


class TestListFeatureSets:
    async def test_returns_all_sets(self):
        set_repo = AsyncMock()
        set_repo.list_all.return_value = [
            _make_set_record("set_a"),
            _make_set_record("set_b"),
        ]

        svc = _make_service(set_repo=set_repo)
        sets = await svc.list_feature_sets()

        assert len(sets) == 2
        names = {s.name for s in sets}
        assert names == {"set_a", "set_b"}

    async def test_returns_empty_list(self):
        set_repo = AsyncMock()
        set_repo.list_all.return_value = []

        svc = _make_service(set_repo=set_repo)
        sets = await svc.list_feature_sets()

        assert sets == []
