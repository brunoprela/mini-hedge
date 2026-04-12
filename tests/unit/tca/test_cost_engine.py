"""Unit tests for TCA CostEngine — pure cost decomposition."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.modules.tca.core.cost_engine import CostEngine, TCAInput, TCAResult

_ZERO = Decimal("0")


def _make_input(**overrides) -> TCAInput:
    defaults = {
        "side": "buy",
        "quantity": Decimal("10000"),
        "filled_quantity": Decimal("10000"),
        "avg_fill_price": Decimal("50.10"),
        "arrival_mid_price": Decimal("50.00"),
        "arrival_spread": Decimal("0.04"),
        "vwap_benchmark": Decimal("50.05"),
        "commission_rate_bps": Decimal("5"),
        "adv": 500000,
        "execution_start": datetime(2026, 4, 10, 10, 0, 0, tzinfo=timezone.utc),
        "execution_end": datetime(2026, 4, 10, 10, 30, 0, tzinfo=timezone.utc),
        "terminal_price": Decimal("50.15"),
    }
    defaults.update(overrides)
    return TCAInput(**defaults)


class TestCostEngineBasicBuy:
    def test_returns_tca_result(self) -> None:
        result = CostEngine.compute(_make_input())
        assert isinstance(result, TCAResult)

    def test_commission_passthrough(self) -> None:
        result = CostEngine.compute(_make_input(commission_rate_bps=Decimal("8")))
        assert result.commission_cost_bps == Decimal("8")

    def test_spread_cost_positive(self) -> None:
        result = CostEngine.compute(_make_input())
        # Half spread / arrival * 10000 = (0.02 / 50) * 10000 = 4.0 bps
        assert result.spread_cost_bps == Decimal("4.0000")

    def test_timing_cost_buy(self) -> None:
        # VWAP > arrival means market moved up → positive timing cost for buyer
        result = CostEngine.compute(_make_input())
        # sign * (50.05 - 50.00) / 50.00 * 10000 = 10.0 bps
        assert result.timing_cost_bps == Decimal("10.0000")

    def test_market_impact_buy(self) -> None:
        result = CostEngine.compute(_make_input())
        # sign * (50.10 - 50.05) / 50.00 * 10000 = 10.0 bps
        assert result.market_impact_cost_bps == Decimal("10.0000")

    def test_implementation_shortfall_is_sum(self) -> None:
        result = CostEngine.compute(_make_input())
        components = (
            result.commission_cost_bps
            + result.spread_cost_bps
            + result.timing_cost_bps
            + result.market_impact_cost_bps
            + result.opportunity_cost_bps
        )
        assert result.implementation_shortfall_bps == components

    def test_opportunity_cost_fully_filled(self) -> None:
        result = CostEngine.compute(_make_input(filled_quantity=Decimal("10000")))
        assert result.opportunity_cost_bps == _ZERO

    def test_total_cost_usd_positive(self) -> None:
        result = CostEngine.compute(_make_input())
        assert result.total_cost_usd > _ZERO

    def test_execution_duration(self) -> None:
        result = CostEngine.compute(_make_input())
        assert result.execution_duration_seconds == 1800  # 30 minutes


class TestCostEngineSell:
    def test_sell_side_reverses_sign(self) -> None:
        result = CostEngine.compute(
            _make_input(
                side="sell",
                avg_fill_price=Decimal("49.90"),
                vwap_benchmark=Decimal("49.95"),
            )
        )
        # For sell: timing = -1 * (49.95 - 50.00) / 50.00 * 10000 = 10.0 bps
        assert result.timing_cost_bps == Decimal("10.0000")


class TestCostEngineEdgeCases:
    def test_zero_arrival_price(self) -> None:
        result = CostEngine.compute(
            _make_input(arrival_mid_price=Decimal("0"))
        )
        assert result.total_cost_bps == _ZERO

    def test_no_vwap_benchmark(self) -> None:
        result = CostEngine.compute(
            _make_input(vwap_benchmark=None)
        )
        assert result.timing_cost_bps == _ZERO
        # Impact falls back to slippage minus spread
        assert result.market_impact_cost_bps >= _ZERO

    def test_partial_fill_has_opportunity_cost(self) -> None:
        result = CostEngine.compute(
            _make_input(
                filled_quantity=Decimal("5000"),
                terminal_price=Decimal("51.00"),
            )
        )
        assert result.opportunity_cost_bps > _ZERO

    def test_no_terminal_price_no_opportunity(self) -> None:
        result = CostEngine.compute(
            _make_input(
                filled_quantity=Decimal("5000"),
                terminal_price=None,
            )
        )
        assert result.opportunity_cost_bps == _ZERO

    def test_participation_rate(self) -> None:
        result = CostEngine.compute(
            _make_input(filled_quantity=Decimal("10000"), adv=500000)
        )
        assert result.participation_rate == Decimal("0.020000")

    def test_no_adv_no_participation(self) -> None:
        result = CostEngine.compute(_make_input(adv=None))
        assert result.participation_rate is None

    def test_zero_adv_no_participation(self) -> None:
        result = CostEngine.compute(_make_input(adv=0))
        assert result.participation_rate is None
