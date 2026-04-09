"""Unit tests for BacktestingService — mocked repo, real engine, real event bus."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.backtesting.core.engine import BacktestEngine
from app.modules.backtesting.interfaces import (
    BacktestConfig,
    BacktestStatus,
    BacktestSummary,
    RebalanceFrequency,
)
from app.modules.backtesting.services import BacktestingService
from app.shared.audit.events import AuditEventType
from app.shared.events import InProcessEventBus
from app.shared.schema_registry import shared_topic
from tests.helpers import EventCapture

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_START = date(2024, 1, 2)
_END = date(2024, 1, 31)

SIMPLE_PRICE_DATA: dict[str, list[tuple[date, Decimal]]] = {
    "AAPL": [
        (date(2024, 1, d), Decimal(str(100 + d)))
        for d in range(2, 32)
        if date(2024, 1, d).weekday() < 5
    ],
    "MSFT": [
        (date(2024, 1, d), Decimal(str(200 + d)))
        for d in range(2, 32)
        if date(2024, 1, d).weekday() < 5
    ],
}


def _make_config(**overrides) -> BacktestConfig:
    defaults = dict(
        strategy_name="test-strategy",
        start_date=_START,
        end_date=_END,
        initial_capital=Decimal("100000"),
        rebalance_frequency=RebalanceFrequency.DAILY,
        universe=["AAPL", "MSFT"],
        slippage_bps=5,
        commission_bps=10,
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


def _make_run_record(
    backtest_id: str = "bt-1", status: str = BacktestStatus.COMPLETED
) -> MagicMock:
    record = MagicMock()
    record.id = backtest_id
    record.strategy_name = "test-strategy"
    record.status = status
    record.results = {
        "total_return": "0.05",
        "annualized_return": "0.06",
        "sharpe_ratio": "1.2",
        "max_drawdown": "0.03",
        "volatility": "0.15",
        "calmar_ratio": "2.0",
        "sortino_ratio": "1.5",
        "win_rate": "0.6",
        "profit_factor": "1.8",
        "total_trades": 10,
        "avg_holding_period_days": "5",
        "monthly_returns": [],
    }
    record.equity_curve = []
    record.trades = []
    record.config = _make_config().model_dump(mode="json")
    record.created_at = datetime(2024, 1, 2, tzinfo=UTC)
    record.completed_at = datetime(2024, 1, 31, tzinfo=UTC)
    return record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(event_bus, [shared_topic("audit")])
    return cap


@pytest.fixture
def repo() -> AsyncMock:
    r = AsyncMock()

    # create() sets record.id as a side-effect
    async def _create(record, *, session=None):
        record.id = "bt-1"
        record.created_at = datetime(2024, 1, 2, tzinfo=UTC)

    r.create.side_effect = _create
    return r


@pytest.fixture
def engine() -> BacktestEngine:
    return BacktestEngine()


@pytest.fixture
def service(
    repo: AsyncMock, engine: BacktestEngine, event_bus: InProcessEventBus
) -> BacktestingService:
    return BacktestingService(
        repo=repo,
        engine=engine,
        session_factory=MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# TestSubmitBacktest
# ---------------------------------------------------------------------------


class TestSubmitBacktest:
    async def test_creates_record_and_returns_summary(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        repo.update_status.return_value = None
        config = _make_config()

        summary = await service.submit_backtest(config, SIMPLE_PRICE_DATA)

        assert isinstance(summary, BacktestSummary)
        assert summary.strategy_name == "test-strategy"
        assert summary.status == BacktestStatus.COMPLETED
        repo.create.assert_called_once()

    async def test_transitions_status_to_running_then_completed(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        repo.update_status.return_value = None
        config = _make_config()

        await service.submit_backtest(config, SIMPLE_PRICE_DATA)

        calls = [call.args[1] for call in repo.update_status.call_args_list]
        assert BacktestStatus.RUNNING in calls
        assert BacktestStatus.COMPLETED in calls

    async def test_publishes_submitted_event(
        self,
        service: BacktestingService,
        repo: AsyncMock,
        capture: EventCapture,
    ):
        repo.update_status.return_value = None
        await service.submit_backtest(_make_config(), SIMPLE_PRICE_DATA)

        submitted = [
            e
            for e in capture.get_by_topic("audit")
            if e.event_type == AuditEventType.BACKTEST_SUBMITTED
        ]
        assert len(submitted) == 1
        assert submitted[0].data["strategy_name"] == "test-strategy"

    async def test_publishes_completed_event(
        self,
        service: BacktestingService,
        repo: AsyncMock,
        capture: EventCapture,
    ):
        repo.update_status.return_value = None
        await service.submit_backtest(_make_config(), SIMPLE_PRICE_DATA)

        completed = [
            e
            for e in capture.get_by_topic("audit")
            if e.event_type == AuditEventType.BACKTEST_COMPLETED
        ]
        assert len(completed) == 1
        assert "total_return" in completed[0].data

    async def test_unknown_signal_raises_value_error(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        with pytest.raises(ValueError, match="Unknown signal function"):
            await service.submit_backtest(
                _make_config(), SIMPLE_PRICE_DATA, signal_name="nonexistent"
            )

    async def test_engine_failure_marks_failed_and_publishes_event(
        self,
        repo: AsyncMock,
        event_bus: InProcessEventBus,
        capture: EventCapture,
    ):
        broken_engine = MagicMock(spec=BacktestEngine)
        broken_engine.run.side_effect = RuntimeError("engine exploded")
        svc = BacktestingService(
            repo=repo, engine=broken_engine, session_factory=MagicMock(), event_bus=event_bus
        )

        with pytest.raises(RuntimeError):
            await svc.submit_backtest(_make_config(), SIMPLE_PRICE_DATA)

        fail_calls = [
            call
            for call in repo.update_status.call_args_list
            if call.args[1] == BacktestStatus.FAILED
        ]
        assert len(fail_calls) == 1

        failed_events = [
            e
            for e in capture.get_by_topic("audit")
            if e.event_type == AuditEventType.BACKTEST_FAILED
        ]
        assert len(failed_events) == 1


# ---------------------------------------------------------------------------
# TestGetBacktestResult
# ---------------------------------------------------------------------------


class TestGetBacktestResult:
    async def test_returns_result_for_existing_id(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        repo.get_by_id.return_value = _make_run_record("bt-42")

        result = await service.get_backtest("bt-42")

        assert result is not None
        assert result.id == "bt-42"
        assert result.status == BacktestStatus.COMPLETED
        repo.get_by_id.assert_called_once_with("bt-42", session=None)

    async def test_returns_none_for_missing_id(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        repo.get_by_id.return_value = None

        result = await service.get_backtest("missing")

        assert result is None


# ---------------------------------------------------------------------------
# TestListBacktests
# ---------------------------------------------------------------------------


class TestListBacktests:
    async def test_returns_all_summaries(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        repo.list_all.return_value = [_make_run_record("bt-1"), _make_run_record("bt-2")]

        results = await service.list_backtests()

        assert len(results) == 2
        assert all(isinstance(r, BacktestSummary) for r in results)

    async def test_passes_status_filter_to_repo(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        repo.list_all.return_value = []

        await service.list_backtests(status="completed", limit=10)

        repo.list_all.assert_called_once_with(status="completed", limit=10, session=None)

    async def test_returns_empty_list_when_none(
        self,
        service: BacktestingService,
        repo: AsyncMock,
    ):
        repo.list_all.return_value = []

        results = await service.list_backtests()

        assert results == []


# ---------------------------------------------------------------------------
# TestBacktestEngine (pure computation)
# ---------------------------------------------------------------------------


class TestBacktestEngine:
    def test_equal_weight_produces_positive_equity_curve(self):
        engine = BacktestEngine()
        config = _make_config()
        from app.modules.backtesting.core.engine import equal_weight_signal

        result = engine.run(config, SIMPLE_PRICE_DATA, equal_weight_signal)

        assert len(result.equity_curve) > 0
        assert result.equity_curve[-1].portfolio_value > Decimal(0)

    def test_total_return_within_reasonable_range(self):
        engine = BacktestEngine()
        config = _make_config()
        from app.modules.backtesting.core.engine import equal_weight_signal

        result = engine.run(config, SIMPLE_PRICE_DATA, equal_weight_signal)

        assert Decimal("-1") < result.total_return < Decimal("10")

    def test_empty_date_range_returns_zero_metrics(self):
        engine = BacktestEngine()
        config = _make_config(start_date=date(2023, 1, 1), end_date=date(2023, 1, 1))
        from app.modules.backtesting.core.engine import equal_weight_signal

        result = engine.run(config, SIMPLE_PRICE_DATA, equal_weight_signal)

        assert result.total_return == Decimal(0)
        assert result.total_trades == 0
        assert result.equity_curve == []

    def test_max_drawdown_non_negative(self):
        engine = BacktestEngine()
        config = _make_config()
        from app.modules.backtesting.core.engine import equal_weight_signal

        result = engine.run(config, SIMPLE_PRICE_DATA, equal_weight_signal)

        assert result.max_drawdown >= Decimal(0)

    def test_trades_generated_on_daily_rebalance(self):
        engine = BacktestEngine()
        config = _make_config(rebalance_frequency=RebalanceFrequency.DAILY)
        from app.modules.backtesting.core.engine import equal_weight_signal

        result = engine.run(config, SIMPLE_PRICE_DATA, equal_weight_signal)

        assert result.total_trades > 0
