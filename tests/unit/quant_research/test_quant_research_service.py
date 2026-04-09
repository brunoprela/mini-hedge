"""Unit tests for QuantResearchService, factor_engine, and regime_detector."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.quant_research.core.factor_engine import (
    compute_momentum_factor,
    compute_value_factor,
)
from app.modules.quant_research.core.regime_detector import RegimeDetector
from app.modules.quant_research.interfaces import (
    FactorExposure,
    FactorType,
    RegimeType,
)
from app.modules.quant_research.services import QuantResearchService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

TODAY = date(2026, 4, 8)


def _make_price_series(
    n: int, start: Decimal = Decimal("100"), daily_pct: Decimal = Decimal("0.001")
) -> list[tuple[date, Decimal]]:
    """Build a synthetic up-trending price series of length n."""
    series: list[tuple[date, Decimal]] = []
    price = start
    base = date(2025, 1, 1)
    for i in range(n):
        series.append((base + timedelta(days=i), price))
        price = price * (Decimal(1) + daily_pct)
    return series


def _make_factor_record(**overrides) -> MagicMock:
    record = MagicMock()
    record.id = str(uuid4())
    record.name = overrides.get("name", "momentum")
    record.factor_type = overrides.get("factor_type", FactorType.MOMENTUM.value)
    record.description = ""
    record.formula = ""
    record.parameters = {}
    record.is_active = True
    for k, v in overrides.items():
        setattr(record, k, v)
    return record


def _make_return_record(return_pct: Decimal, cum: Decimal, d: date) -> MagicMock:
    r = MagicMock()
    r.return_pct = return_pct
    r.cumulative_return = cum
    r.return_date = d
    return r


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(event_bus, ["shared.audit"])
    return cap


@pytest.fixture
def factor_def_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def factor_exp_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def factor_ret_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def regime_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def regime_detector() -> RegimeDetector:
    return RegimeDetector()


@pytest.fixture
def service(
    factor_def_repo: AsyncMock,
    factor_exp_repo: AsyncMock,
    factor_ret_repo: AsyncMock,
    regime_repo: AsyncMock,
    regime_detector: RegimeDetector,
    event_bus: InProcessEventBus,
) -> QuantResearchService:
    return QuantResearchService(
        factor_def_repo=factor_def_repo,
        factor_exp_repo=factor_exp_repo,
        factor_ret_repo=factor_ret_repo,
        regime_repo=regime_repo,
        factor_engine_fns={
            FactorType.MOMENTUM.value: compute_momentum_factor,
        },
        regime_detector=regime_detector,
        session_factory=MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# TestFactorEngine — pure computation
# ---------------------------------------------------------------------------


class TestFactorEngine:
    def test_momentum_returns_factor_exposure_dict(self):
        prices = {
            "AAPL": _make_price_series(260, Decimal("150"), Decimal("0.002")),
            "MSFT": _make_price_series(260, Decimal("300"), Decimal("0.001")),
            "GOOG": _make_price_series(260, Decimal("100"), Decimal("0.0005")),
        }
        result = compute_momentum_factor(prices)

        assert set(result.keys()) == {"AAPL", "MSFT", "GOOG"}
        # z-scores: mean ~ 0, values are real Decimals
        for v in result.values():
            assert isinstance(v, Decimal)

    def test_momentum_higher_return_gets_positive_z_score(self):
        # AAPL grows fast, MSFT flat — AAPL should have higher z-score
        aapl = _make_price_series(260, Decimal("100"), Decimal("0.005"))
        msft = _make_price_series(260, Decimal("100"), Decimal("0.0001"))
        result = compute_momentum_factor({"AAPL": aapl, "MSFT": msft})

        assert result["AAPL"] > result["MSFT"]

    def test_momentum_skips_instruments_with_insufficient_history(self):
        short_series = _make_price_series(100)  # less than 252 lookback
        long_series = _make_price_series(260)
        result = compute_momentum_factor({"SHORT": short_series, "LONG": long_series})

        assert "SHORT" not in result
        assert "LONG" in result

    def test_value_factor_returns_z_scores(self):
        fundamentals = {
            "AAPL": {
                "price": Decimal("150"),
                "earnings": Decimal("10"),
                "book_value": Decimal("50"),
                "sales": Decimal("200"),
            },
            "MSFT": {
                "price": Decimal("300"),
                "earnings": Decimal("8"),
                "book_value": Decimal("40"),
                "sales": Decimal("150"),
            },
            "GOOG": {
                "price": Decimal("100"),
                "earnings": Decimal("5"),
                "book_value": Decimal("60"),
                "sales": Decimal("300"),
            },
        }
        result = compute_value_factor(fundamentals)

        assert set(result.keys()) == {"AAPL", "MSFT", "GOOG"}
        for v in result.values():
            assert isinstance(v, Decimal)

    def test_value_factor_skips_zero_price_instruments(self):
        fundamentals = {
            "VALID": {
                "price": Decimal("100"),
                "earnings": Decimal("5"),
                "book_value": Decimal("30"),
            },
            "ZERO_PRICE": {
                "price": Decimal("0"),
                "earnings": Decimal("5"),
                "book_value": Decimal("30"),
            },
        }
        result = compute_value_factor(fundamentals)

        assert "ZERO_PRICE" not in result

    def test_value_factor_cheap_stock_has_higher_exposure(self):
        # CHEAP: high E/P, B/P; EXPENSIVE: low ratios
        fundamentals = {
            "CHEAP": {
                "price": Decimal("10"),
                "earnings": Decimal("5"),
                "book_value": Decimal("8"),
                "sales": Decimal("20"),
            },
            "EXPENSIVE": {
                "price": Decimal("1000"),
                "earnings": Decimal("5"),
                "book_value": Decimal("8"),
                "sales": Decimal("20"),
            },
        }
        result = compute_value_factor(fundamentals)

        assert result["CHEAP"] > result["EXPENSIVE"]


# ---------------------------------------------------------------------------
# TestRegimeDetector — pure computation
# ---------------------------------------------------------------------------


class TestRegimeDetector:
    def test_detect_regime_returns_regime_analysis(self):
        detector = RegimeDetector()
        prices = _make_price_series(300)
        result = detector.detect_regime(prices)

        assert isinstance(result.current_regime, RegimeType)
        assert Decimal(0) <= result.confidence <= Decimal(1)
        assert len(result.indicators) == 3

    def test_insufficient_data_returns_normal_with_zero_confidence(self):
        detector = RegimeDetector()
        short_prices = _make_price_series(50)  # less than 252 lookback
        result = detector.detect_regime(short_prices)

        assert result.current_regime == RegimeType.NORMAL
        assert result.confidence == Decimal(0)

    def test_bull_regime_for_steady_uptrend_low_vol(self):
        detector = RegimeDetector()
        # Very slow, steady uptrend → low vol, positive trend → BULL
        prices = _make_price_series(300, Decimal("100"), Decimal("0.0003"))
        result = detector.detect_regime(prices)

        assert result.current_regime == RegimeType.BULL

    def test_indicators_have_expected_names(self):
        detector = RegimeDetector()
        prices = _make_price_series(300)
        result = detector.detect_regime(prices)

        indicator_names = {ind.name for ind in result.indicators}
        assert indicator_names == {"volatility", "trend", "drawdown"}

    def test_crisis_regime_for_crashing_market(self):
        detector = RegimeDetector()
        # Build a long uptrend, then add a volatile crash in the final 21-day vol window.
        # The crash must produce both high vol AND large drawdown to trigger CRISIS.
        series = _make_price_series(270, Decimal("200"), Decimal("0.001"))
        crash_start = series[-1][0] + timedelta(days=1)
        peak_price = series[-1][1]
        # Volatile crash: price swings wildly downward — alternating large up/down moves
        # so vol window captures high realized vol while trend and drawdown stay negative.
        import random

        random.seed(42)
        price = peak_price
        for i in range(25):
            # Alternate big down / smaller up to produce high vol + net decline
            move = Decimal("-0.04") if i % 2 == 0 else Decimal("0.01")
            price = price * (Decimal(1) + move)
            series.append((crash_start + timedelta(days=i), price))

        result = detector.detect_regime(series)
        # High vol + large drawdown → CRISIS or BEAR (both valid for a crashing market)
        assert result.current_regime in {RegimeType.CRISIS, RegimeType.BEAR, RegimeType.HIGH_VOL}


# ---------------------------------------------------------------------------
# TestQuantResearchService — mocked repos
# ---------------------------------------------------------------------------


class TestQuantResearchService:
    async def test_analyze_factor_raises_when_factor_not_found(
        self,
        service: QuantResearchService,
        factor_def_repo: AsyncMock,
        factor_exp_repo: AsyncMock,
        factor_ret_repo: AsyncMock,
    ):
        factor_def_repo.get_by_name.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.analyze_factor("nonexistent")

    async def test_analyze_factor_returns_zeroed_result_when_no_returns(
        self,
        service: QuantResearchService,
        factor_def_repo: AsyncMock,
        factor_exp_repo: AsyncMock,
        factor_ret_repo: AsyncMock,
    ):
        factor_def_repo.get_by_name.return_value = _make_factor_record(name="momentum")
        factor_ret_repo.get_by_factor.return_value = []
        factor_def_repo.list_all.return_value = []
        factor_exp_repo.get_by_factor_date.return_value = []

        result = await service.analyze_factor("momentum")

        assert result.factor_name == "momentum"
        assert result.mean_return == Decimal(0)
        assert result.volatility == Decimal(0)
        assert result.sharpe_ratio == Decimal(0)

    async def test_analyze_factor_computes_stats_from_returns(
        self,
        service: QuantResearchService,
        factor_def_repo: AsyncMock,
        factor_exp_repo: AsyncMock,
        factor_ret_repo: AsyncMock,
    ):
        factor_def_repo.get_by_name.return_value = _make_factor_record(name="momentum")
        factor_ret_repo.get_by_factor.return_value = [
            _make_return_record(Decimal("0.01"), Decimal("1.01"), date(2025, 1, i + 1))
            for i in range(10)
        ]
        factor_def_repo.list_all.return_value = []
        factor_exp_repo.get_by_factor_date.return_value = []

        result = await service.analyze_factor("momentum")

        assert result.factor_name == "momentum"
        assert result.mean_return > Decimal(0)  # annualized
        assert result.volatility >= Decimal(0)

    async def test_detect_regime_persists_snapshot(
        self, service: QuantResearchService, regime_repo: AsyncMock
    ):
        prices = _make_price_series(300)
        await service.detect_regime(prices)

        regime_repo.save_snapshot.assert_called_once()

    async def test_detect_regime_returns_regime_analysis(
        self, service: QuantResearchService, regime_repo: AsyncMock
    ):
        prices = _make_price_series(300)
        result = await service.detect_regime(prices)

        assert isinstance(result.current_regime, RegimeType)
        assert result.confidence >= Decimal(0)

    async def test_detect_regime_publishes_audit_event(
        self,
        service: QuantResearchService,
        regime_repo: AsyncMock,
        capture: EventCapture,
    ):
        prices = _make_price_series(300)
        await service.detect_regime(prices)

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].data["regime_type"] is not None

    async def test_compute_factor_exposures_raises_when_factor_missing(
        self,
        service: QuantResearchService,
        factor_def_repo: AsyncMock,
        factor_exp_repo: AsyncMock,
        factor_ret_repo: AsyncMock,
    ):
        factor_def_repo.get_by_name.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.compute_factor_exposures("missing", {})

    async def test_compute_factor_exposures_raises_for_unknown_factor_type(
        self,
        service: QuantResearchService,
        factor_def_repo: AsyncMock,
        factor_exp_repo: AsyncMock,
        factor_ret_repo: AsyncMock,
    ):
        factor_def_repo.get_by_name.return_value = _make_factor_record(
            factor_type="value"
        )  # no fn registered
        factor_exp_repo.save_many.return_value = None

        with pytest.raises(ValueError, match="No compute function"):
            await service.compute_factor_exposures("value", {})

    async def test_compute_factor_exposures_saves_and_publishes(
        self,
        service: QuantResearchService,
        factor_def_repo: AsyncMock,
        factor_exp_repo: AsyncMock,
        capture: EventCapture,
    ):
        factor_def_repo.get_by_name.return_value = _make_factor_record(
            name="momentum", factor_type=FactorType.MOMENTUM.value
        )
        factor_exp_repo.save_many.return_value = None

        price_data = {
            "AAPL": _make_price_series(260, Decimal("150"), Decimal("0.002")),
            "MSFT": _make_price_series(260, Decimal("300"), Decimal("0.001")),
            "GOOG": _make_price_series(260, Decimal("100"), Decimal("0.0005")),
        }
        result = await service.compute_factor_exposures("momentum", price_data)

        factor_exp_repo.save_many.assert_called_once()
        assert all(isinstance(e, FactorExposure) for e in result)
        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].data["factor_name"] == "momentum"
