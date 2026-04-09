"""Unit tests for FeatureStoreService and FeatureComputeEngine."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.feature_store.core.compute_engine import FeatureComputeEngine
from app.modules.feature_store.interfaces import (
    ComputeMethod,
    FeatureDefinition,
    FeatureStatus,
    FeatureType,
)
from app.modules.feature_store.models.feature_definition import FeatureDefinitionRecord
from app.modules.feature_store.services import FeatureStoreService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

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


def _make_feature_def(
    name: str = "test_feature", expression: str = "sma(prices, 5)"
) -> FeatureDefinition:
    return FeatureDefinition(
        id=uuid4(),
        name=name,
        description="",
        feature_type=FeatureType.NUMERIC,
        compute_method=ComputeMethod.PYTHON,
        expression=expression,
        dependencies=[],
        entity_type="instrument",
        version=1,
        status=FeatureStatus.ACTIVE,
        tags=[],
        created_at=NOW,
        updated_at=NOW,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> FeatureComputeEngine:
    return FeatureComputeEngine()


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(event_bus, ["shared.audit"])
    return cap


def _seed_def_record(record) -> None:
    """Set server-side fields that would normally be set by PostgreSQL."""
    record.id = str(uuid4())
    # created_at / updated_at are set explicitly by register_feature, so no override needed


@pytest.fixture
def definition_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def value_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def set_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    definition_repo: AsyncMock,
    value_repo: AsyncMock,
    set_repo: AsyncMock,
    engine: FeatureComputeEngine,
    event_bus: InProcessEventBus,
) -> FeatureStoreService:
    return FeatureStoreService(
        definition_repo=definition_repo,
        value_repo=value_repo,
        set_repo=set_repo,
        compute_engine=engine,
        session_factory=MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# FeatureComputeEngine — pure computation tests
# ---------------------------------------------------------------------------


class TestFeatureComputeEngine:
    PRICES = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0]

    def test_sma_last_window(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="sma(prices, 3)")
        result = engine.compute(defn, {"prices": self.PRICES})
        # last 3: [105, 104, 106] → avg = 315/3 = 105.0
        assert result == Decimal("105.0")

    def test_sma_full_window(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="sma(prices, 7)")
        result = engine.compute(defn, {"prices": self.PRICES})
        expected = Decimal(str(round(sum(self.PRICES) / 7, 8)))
        assert result == expected

    def test_ema_returns_decimal(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="ema(prices, 3)")
        result = engine.compute(defn, {"prices": self.PRICES})
        assert isinstance(result, Decimal)
        assert result > Decimal("0")

    def test_rsi_all_gains_returns_100(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="rsi(prices, 5)")
        strictly_up = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        result = engine.compute(defn, {"prices": strictly_up})
        assert result == Decimal("100.0")

    def test_rsi_bounded_range(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="rsi(prices, 5)")
        result = engine.compute(defn, {"prices": self.PRICES})
        assert Decimal("0") <= result <= Decimal("100")

    def test_returns_positive_when_price_rises(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="returns(prices, 1)")
        prices = [100.0, 110.0]
        result = engine.compute(defn, {"prices": prices})
        assert result == Decimal("0.1")

    def test_returns_negative_when_price_falls(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="returns(prices, 1)")
        prices = [100.0, 90.0]
        result = engine.compute(defn, {"prices": prices})
        assert result == Decimal("-0.1")

    def test_volatility_constant_prices_is_zero(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="volatility(prices, 5)")
        flat = [100.0] * 10
        result = engine.compute(defn, {"prices": flat})
        assert result == Decimal("0.0")

    def test_volatility_positive_for_varying_prices(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="volatility(prices, 5)")
        result = engine.compute(defn, {"prices": self.PRICES})
        assert result > Decimal("0")

    def test_unknown_function_returns_none(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="nonexistent_fn(prices, 5)")
        result = engine.compute(defn, {"prices": self.PRICES})
        assert result is None

    def test_decimal_prices_are_cast_to_float(self, engine: FeatureComputeEngine):
        defn = _make_feature_def(expression="sma(prices, 3)")
        decimal_prices = [Decimal("100"), Decimal("102"), Decimal("104")]
        result = engine.compute(defn, {"prices": decimal_prices})
        assert result == Decimal("102.0")

    def test_compute_batch_multiple_entities(self, engine: FeatureComputeEngine):
        sma_defn = _make_feature_def(name="sma_5", expression="sma(prices, 3)")
        entities = {
            "AAPL": {"prices": [100.0, 102.0, 104.0]},
            "MSFT": {"prices": [200.0, 202.0, 204.0]},
        }
        results = engine.compute_batch([sma_defn], entities)
        assert results["AAPL"]["sma_5"] == Decimal("102.0")
        assert results["MSFT"]["sma_5"] == Decimal("202.0")


# ---------------------------------------------------------------------------
# register_feature
# ---------------------------------------------------------------------------


class TestRegisterFeature:
    async def test_returns_feature_definition(
        self,
        service: FeatureStoreService,
        definition_repo: AsyncMock,
        value_repo: AsyncMock,
    ):
        definition_repo.create.side_effect = lambda r, **kw: _seed_def_record(r)

        defn = await service.register_feature(
            name="sma_20",
            description="20-day SMA",
            feature_type=FeatureType.NUMERIC,
            compute_method=ComputeMethod.PYTHON,
            expression="sma(prices, 20)",
            entity_type="instrument",
            tags=["momentum"],
        )

        assert defn.name == "sma_20"
        assert defn.feature_type == FeatureType.NUMERIC
        assert defn.status == FeatureStatus.ACTIVE
        assert defn.tags == ["momentum"]

    async def test_publishes_audit_event(
        self,
        service: FeatureStoreService,
        definition_repo: AsyncMock,
        value_repo: AsyncMock,
        capture: EventCapture,
    ):
        definition_repo.create.side_effect = lambda r, **kw: _seed_def_record(r)

        await service.register_feature(
            name="rsi_14",
            description="14-day RSI",
            feature_type=FeatureType.NUMERIC,
            compute_method=ComputeMethod.PYTHON,
            expression="rsi(prices, 14)",
            entity_type="instrument",
        )

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].data["name"] == "rsi_14"
        assert audit_events[0].data["entity_type"] == "instrument"


# ---------------------------------------------------------------------------
# list_features
# ---------------------------------------------------------------------------


class TestListFeatures:
    async def test_returns_all_features(
        self,
        service: FeatureStoreService,
        definition_repo: AsyncMock,
        value_repo: AsyncMock,
    ):
        definition_repo.list_all.return_value = [
            _make_def_record("sma_5"),
            _make_def_record("ema_10"),
            _make_def_record("rsi_14"),
        ]

        features = await service.list_features()

        assert len(features) == 3
        names = {f.name for f in features}
        assert names == {"sma_5", "ema_10", "rsi_14"}

    async def test_filters_by_entity_type(
        self,
        service: FeatureStoreService,
        definition_repo: AsyncMock,
        value_repo: AsyncMock,
    ):
        definition_repo.list_all.return_value = [_make_def_record("vol_30")]

        features = await service.list_features(entity_type="instrument")

        definition_repo.list_all.assert_called_once_with(
            entity_type="instrument", status=None, session=None
        )
        assert len(features) == 1


# ---------------------------------------------------------------------------
# compute_feature (single)
# ---------------------------------------------------------------------------


class TestComputeFeature:
    async def test_computes_sma_and_stores_value(
        self, service: FeatureStoreService, definition_repo: AsyncMock, value_repo: AsyncMock
    ):
        record = _make_def_record("sma_5", expression="sma(prices, 3)")
        definition_repo.get_by_name.return_value = record

        result = await service.compute_feature("sma_5", "AAPL", {"prices": [100.0, 102.0, 104.0]})

        assert result.feature_name == "sma_5"
        assert result.entity_id == "AAPL"
        assert result.value == Decimal("102.0")
        value_repo.save_many.assert_called_once()

    async def test_unknown_feature_raises(
        self,
        service: FeatureStoreService,
        definition_repo: AsyncMock,
        value_repo: AsyncMock,
    ):
        definition_repo.get_by_name.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await service.compute_feature("ghost_feature", "AAPL", {})


# ---------------------------------------------------------------------------
# compute_features_batch — event publishing
# ---------------------------------------------------------------------------


class TestComputeFeaturesBatch:
    async def test_publishes_audit_event_after_batch(
        self,
        service: FeatureStoreService,
        definition_repo: AsyncMock,
        value_repo: AsyncMock,
        capture: EventCapture,
    ):
        rec = _make_def_record("sma_3", expression="sma(prices, 3)")
        definition_repo.get_by_name.return_value = rec

        await service.compute_features_batch(
            feature_names=["sma_3"],
            entities_data={"AAPL": {"prices": [100.0, 102.0, 104.0]}},
        )

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].data["entity_count"] == 1
        assert "sma_3" in audit_events[0].data["feature_names"]
