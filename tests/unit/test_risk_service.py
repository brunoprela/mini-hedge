"""Unit tests for RiskService — mocked deps, verifies orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.risk_engine.interface import (
    StressScenario,
    StressScenarioType,
    VaRMethod,
)
from app.modules.risk_engine.service import RiskService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_position(iid: str, qty: Decimal, mv: Decimal):
    pos = MagicMock()
    pos.instrument_id = iid
    pos.quantity = qty
    pos.market_value = mv
    return pos


def _mock_instrument(
    ticker: str, sector: str = "Technology", vol: float = 0.25, drift: float = 0.08
):
    inst = MagicMock()
    inst.ticker = ticker
    inst.sector = sector
    inst.annual_volatility = vol
    inst.annual_drift = drift
    return inst


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def risk_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_latest_snapshot.return_value = None

    # save_snapshot should assign an id to the record (mimicking DB default)
    async def _save_snapshot(record, *, session=None):
        if record.id is None:
            record.id = uuid4()

    repo.save_snapshot.side_effect = _save_snapshot
    return repo


@pytest.fixture
def position_service() -> AsyncMock:
    svc = AsyncMock()
    svc.get_by_portfolio.return_value = [
        _mock_position("AAPL", Decimal("100"), Decimal("500000")),
        _mock_position("JNJ", Decimal("200"), Decimal("300000")),
    ]
    return svc


@pytest.fixture
def market_data_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def security_master_service() -> AsyncMock:
    svc = AsyncMock()
    svc.get_all_active.return_value = [
        _mock_instrument("AAPL", "Technology"),
        _mock_instrument("JNJ", "Healthcare"),
    ]
    return svc


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def service(
    risk_repo,
    position_service,
    market_data_service,
    security_master_service,
    event_bus,
) -> RiskService:
    return RiskService(
        risk_repo=risk_repo,
        position_service=position_service,
        market_data_service=market_data_service,
        security_master_service=security_master_service,
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# calculate_var
# ---------------------------------------------------------------------------


class TestCalculateVaR:
    async def test_historical_var_returns_result(self, service, risk_repo):
        pid = uuid4()
        result = await service.calculate_var(pid, VaRMethod.HISTORICAL)
        assert result.portfolio_id == pid
        assert result.method == VaRMethod.HISTORICAL
        assert result.var_amount > 0

    async def test_parametric_var_returns_result(self, service):
        result = await service.calculate_var(uuid4(), VaRMethod.PARAMETRIC)
        assert result.method == VaRMethod.PARAMETRIC
        assert result.var_amount > 0

    async def test_var_persisted(self, service, risk_repo):
        await service.calculate_var(uuid4())
        risk_repo.save_var_result.assert_called_once()

    async def test_empty_portfolio_returns_zero(self, service, position_service):
        position_service.get_by_portfolio.return_value = []
        result = await service.calculate_var(uuid4())
        assert result.var_amount == Decimal(0)


# ---------------------------------------------------------------------------
# stress test
# ---------------------------------------------------------------------------


class TestStressTest:
    async def test_stress_test_returns_result(self, service):
        scenario = StressScenario(
            name="Crash",
            scenario_type=StressScenarioType.PREDEFINED,
            shocks={"market": -0.20},
        )
        result = await service.run_stress_test(uuid4(), scenario)
        assert result.total_pnl_impact < 0  # negative shock
        assert len(result.position_impacts) == 2

    async def test_stress_test_persisted(self, service, risk_repo):
        scenario = StressScenario(
            name="Crash",
            scenario_type=StressScenarioType.PREDEFINED,
            shocks={"market": -0.10},
        )
        await service.run_stress_test(uuid4(), scenario)
        risk_repo.save_stress_result.assert_called_once()


# ---------------------------------------------------------------------------
# factor model
# ---------------------------------------------------------------------------


class TestFactorModel:
    async def test_factor_decomposition_returns_result(self, service):
        result = await service.calculate_factor_model(uuid4())
        factor_names = [fe.factor_name for fe in result.factor_exposures]
        assert "Market" in factor_names
        assert "Idiosyncratic" in factor_names


# ---------------------------------------------------------------------------
# take_snapshot
# ---------------------------------------------------------------------------


class TestTakeSnapshot:
    async def test_snapshot_persisted(self, service, risk_repo):
        result = await service.take_snapshot(uuid4(), fund_slug="alpha")
        risk_repo.save_snapshot.assert_called_once()
        assert result.var_95_1d > 0
        assert result.var_99_1d > 0
        assert result.var_99_1d > result.var_95_1d

    async def test_snapshot_publishes_event(self, service, event_bus):
        capture = EventCapture()
        capture.wire_to_bus(event_bus, ["fund-alpha.risk.updated"])

        await service.take_snapshot(uuid4(), fund_slug="alpha")

        events = capture.get_by_topic("risk.updated")
        assert len(events) == 1

    async def test_snapshot_no_event_without_fund_slug(self, service, event_bus):
        capture = EventCapture()
        capture.wire_to_bus(event_bus, ["fund-alpha.risk.updated"])

        await service.take_snapshot(uuid4(), fund_slug=None)

        events = capture.get_by_topic("risk.updated")
        assert len(events) == 0


# ---------------------------------------------------------------------------
# get_latest_snapshot
# ---------------------------------------------------------------------------


class TestGetLatestSnapshot:
    async def test_returns_none_when_empty(self, service, risk_repo):
        risk_repo.get_latest_snapshot.return_value = None
        result = await service.get_latest_snapshot(uuid4())
        assert result is None

    async def test_returns_snapshot(self, service, risk_repo):
        record = MagicMock()
        record.id = uuid4()
        record.portfolio_id = uuid4()
        record.nav = Decimal("800000")
        record.var_95_1d = Decimal("15000")
        record.var_99_1d = Decimal("25000")
        record.expected_shortfall_95 = Decimal("20000")
        record.max_drawdown = Decimal("0")
        record.sharpe_ratio = None
        record.snapshot_at = datetime.now(UTC)
        risk_repo.get_latest_snapshot.return_value = record

        result = await service.get_latest_snapshot(uuid4())
        assert result is not None
        assert result.nav == Decimal("800000")
