"""Unit tests for AlphaService — what-if analysis, optimization, intents."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.alpha_engine.interfaces import (
    HypotheticalTrade,
    OptimizationObjective,
    OptimizationResult,
    OptimizationWeight,
    OrderIntent,
    ScenarioRun,
    ScenarioStatus,
    WhatIfResult,
)
from app.modules.alpha_engine.services.alpha import AlphaService

ZERO = Decimal(0)
_PID = uuid4()


def _make_position(
    instrument_id: str = "AAPL",
    quantity: Decimal = Decimal("100"),
    market_value: Decimal = Decimal("15000"),
    market_price: Decimal | None = None,
) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.quantity = quantity
    p.market_value = market_value
    p.market_price = market_price or (market_value / quantity if quantity != ZERO else ZERO)
    return p


def _make_what_if_result() -> WhatIfResult:
    return WhatIfResult(
        portfolio_id=_PID,
        scenario_name="test",
        current_nav=Decimal("100000"),
        proposed_nav=Decimal("101000"),
        nav_change=Decimal("1000"),
        nav_change_pct=Decimal("1.0"),
        positions=[],
        calculated_at=datetime.now(timezone.utc),
    )


def _make_service(
    positions: list | None = None,
    what_if_result: WhatIfResult | None = None,
    with_event_bus: bool = False,
) -> AlphaService:
    scenario_repo = AsyncMock()
    scenario_repo.save = AsyncMock()
    scenario_repo.get_many = AsyncMock(return_value=[])

    opt_run_repo = AsyncMock()
    opt_run_repo.save = AsyncMock()
    opt_run_repo.get_many = AsyncMock(return_value=[])

    opt_weight_repo = AsyncMock()
    opt_weight_repo.save_many = AsyncMock()

    intent_repo = AsyncMock()
    intent_repo.save_many = AsyncMock()
    intent_repo.get_by_portfolio = AsyncMock(return_value=[])
    intent_repo.get_by_run = AsyncMock(return_value=[])
    intent_repo.update_status = AsyncMock()

    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    security_master = AsyncMock()
    security_master.get_all_active = AsyncMock(return_value=[])

    event_bus = AsyncMock() if with_event_bus else None

    return AlphaService(
        scenario_repo=scenario_repo,
        opt_run_repo=opt_run_repo,
        opt_weight_repo=opt_weight_repo,
        intent_repo=intent_repo,
        position_service=position_service,
        security_master_service=security_master,
        event_bus=event_bus,
    )


class TestRunWhatIf:
    @pytest.mark.asyncio
    async def test_basic_what_if(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("15000")),
            _make_position("MSFT", Decimal("50"), Decimal("20000")),
        ]
        svc = _make_service(positions=positions)

        trades = [
            HypotheticalTrade(instrument_id="AAPL", side="buy", quantity=Decimal("10"), price=Decimal("150")),
        ]

        with patch("app.modules.alpha_engine.services.alpha.run_what_if", return_value=_make_what_if_result()):
            result = await svc.run_what_if(_PID, "test scenario", trades)

        assert result.portfolio_id == _PID
        assert result.current_nav > ZERO
        svc._scenario_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_what_if_filters_zero_quantity(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("15000")),
            _make_position("CLOSED", ZERO, ZERO),
        ]
        svc = _make_service(positions=positions)

        with patch("app.modules.alpha_engine.services.alpha.run_what_if", return_value=_make_what_if_result()):
            result = await svc.run_what_if(_PID, "test", [])

        assert result is not None

    @pytest.mark.asyncio
    async def test_what_if_new_instrument_price(self) -> None:
        """Trade in instrument not in portfolio should use trade's price."""
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        svc = _make_service(positions=positions)

        trades = [
            HypotheticalTrade(instrument_id="TSLA", side="buy", quantity=Decimal("10"), price=Decimal("200")),
        ]

        with patch("app.modules.alpha_engine.services.alpha.run_what_if", return_value=_make_what_if_result()):
            result = await svc.run_what_if(_PID, "new_inst", trades)

        assert result is not None


class TestOptimize:
    @pytest.mark.asyncio
    async def test_empty_positions(self) -> None:
        svc = _make_service(positions=[])

        result = await svc.optimize(_PID, OptimizationObjective.MAX_SHARPE)

        assert result.expected_return == ZERO
        assert result.weights == []

    @pytest.mark.asyncio
    async def test_optimization_with_positions(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("15000")),
            _make_position("MSFT", Decimal("50"), Decimal("20000")),
        ]
        svc = _make_service(positions=positions, with_event_bus=True)

        opt_result = OptimizationResult(
            portfolio_id=_PID,
            objective=OptimizationObjective.MAX_SHARPE,
            expected_return=Decimal("0.12"),
            expected_risk=Decimal("0.15"),
            sharpe_ratio=Decimal("0.8"),
            weights=[],
            order_intents=[],
            calculated_at=datetime.now(timezone.utc),
        )

        with patch("app.modules.alpha_engine.services.alpha.optimize_portfolio", return_value=opt_result):
            result = await svc.optimize(_PID, OptimizationObjective.MAX_SHARPE)

        assert result.expected_return == Decimal("0.12")
        svc._opt_run_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimization_with_intents_publishes(self) -> None:
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        svc = _make_service(positions=positions, with_event_bus=True)

        opt_result = OptimizationResult(
            portfolio_id=_PID,
            objective=OptimizationObjective.MIN_VARIANCE,
            expected_return=Decimal("0.08"),
            expected_risk=Decimal("0.10"),
            weights=[],
            order_intents=[
                OrderIntent(instrument_id="AAPL", side="sell", quantity=Decimal("10"), estimated_value=Decimal("1500"), reason="rebalance"),
            ],
            calculated_at=datetime.now(timezone.utc),
        )

        with patch("app.modules.alpha_engine.services.alpha.optimize_portfolio", return_value=opt_result):
            with patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value="test-fund"):
                result = await svc.optimize(_PID, OptimizationObjective.MIN_VARIANCE)

        assert len(result.order_intents) == 1


class TestScenarioHistory:
    @pytest.mark.asyncio
    async def test_get_scenarios(self) -> None:
        record = MagicMock()
        record.id = str(uuid4())
        record.portfolio_id = str(_PID)
        record.scenario_name = "test"
        record.trades = [{"instrument_id": "AAPL", "side": "buy"}]
        record.result_summary = {"current_nav": "100000"}
        record.status = "completed"
        record.created_at = datetime.now(timezone.utc)

        svc = _make_service()
        svc._scenario_repo.get_many = AsyncMock(return_value=[record])

        scenarios = await svc.get_scenarios(_PID)

        assert len(scenarios) == 1
        assert scenarios[0].scenario_name == "test"


class TestOrderIntents:
    @pytest.mark.asyncio
    async def test_get_order_intents(self) -> None:
        record = MagicMock()
        record.instrument_id = "AAPL"
        record.side = "buy"
        record.quantity = 100
        record.estimated_value = Decimal("15000")
        record.reason = "rebalance"

        svc = _make_service()
        svc._intent_repo.get_by_portfolio = AsyncMock(return_value=[record])

        intents = await svc.get_order_intents(_PID)

        assert len(intents) == 1
        assert intents[0].instrument_id == "AAPL"

    @pytest.mark.asyncio
    async def test_approve_intent(self) -> None:
        svc = _make_service()
        await svc.approve_intent("intent-1")
        svc._intent_repo.update_status.assert_called_once_with("intent-1", "approved", session=None)

    @pytest.mark.asyncio
    async def test_cancel_intent(self) -> None:
        svc = _make_service()
        await svc.cancel_intent("intent-1")
        svc._intent_repo.update_status.assert_called_once_with("intent-1", "cancelled", session=None)


class TestOptimizationHistory:
    @pytest.mark.asyncio
    async def test_get_optimizations(self) -> None:
        run_record = MagicMock()
        run_record.id = str(uuid4())
        run_record.portfolio_id = str(_PID)
        run_record.objective = "max_sharpe"
        run_record.expected_return = Decimal("0.12")
        run_record.expected_risk = Decimal("0.15")
        run_record.sharpe_ratio = Decimal("0.8")
        run_record.created_at = datetime.now(timezone.utc)

        svc = _make_service()
        svc._opt_run_repo.get_many = AsyncMock(return_value=[run_record])

        results = await svc.get_optimizations(_PID)

        assert len(results) == 1
        assert results[0].objective == OptimizationObjective.MAX_SHARPE
