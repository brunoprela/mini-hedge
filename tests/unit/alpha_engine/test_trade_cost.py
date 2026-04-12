"""Unit tests for TradeCostModel — commission, spread, market impact estimation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.alpha_engine.core.trade_cost import TradeCostBreakdown, TradeCostModel

ZERO = Decimal(0)


class TestTradeCostBreakdown:
    def test_total(self) -> None:
        b = TradeCostBreakdown(
            commission=Decimal("5"),
            spread_cost=Decimal("3"),
            market_impact=Decimal("2"),
        )
        assert b.total == Decimal("10")

    def test_total_bps(self) -> None:
        b = TradeCostBreakdown(
            commission=Decimal("5"),
            spread_cost=Decimal("3"),
            market_impact=Decimal("2"),
        )
        assert b.total_bps == Decimal("10")

    def test_zero_components(self) -> None:
        b = TradeCostBreakdown(commission=ZERO, spread_cost=ZERO, market_impact=ZERO)
        assert b.total == ZERO


class TestTradeCostModel:
    def test_default_params(self) -> None:
        m = TradeCostModel()
        assert m.commission_bps == Decimal("5")
        assert m.spread_bps == Decimal("3")
        assert m.impact_coefficient == Decimal("0.1")

    def test_estimate_no_adv(self) -> None:
        m = TradeCostModel(commission_bps=Decimal("10"), spread_bps=Decimal("5"))
        result = m.estimate(Decimal("100000"))

        # commission = 100000 * 10 / 10000 = 100
        assert result.commission == Decimal("100.00000000")
        # spread = 100000 * 5 / 10000 = 50
        assert result.spread_cost == Decimal("50.00000000")
        assert result.market_impact == ZERO

    def test_estimate_with_adv(self) -> None:
        m = TradeCostModel(
            commission_bps=Decimal("5"),
            spread_bps=Decimal("3"),
            impact_coefficient=Decimal("0.1"),
        )
        result = m.estimate(Decimal("100000"), adv=Decimal("1000000"))

        assert result.commission > ZERO
        assert result.spread_cost > ZERO
        assert result.market_impact > ZERO

    def test_estimate_negative_notional_uses_absolute(self) -> None:
        m = TradeCostModel(commission_bps=Decimal("10"), spread_bps=Decimal("5"))
        positive = m.estimate(Decimal("100000"))
        negative = m.estimate(Decimal("-100000"))

        assert positive.commission == negative.commission
        assert positive.spread_cost == negative.spread_cost

    def test_estimate_zero_notional(self) -> None:
        m = TradeCostModel()
        result = m.estimate(ZERO)

        assert result.commission == ZERO
        assert result.spread_cost == ZERO
        assert result.market_impact == ZERO

    def test_estimate_adv_zero(self) -> None:
        """ADV of zero should produce no market impact."""
        m = TradeCostModel()
        result = m.estimate(Decimal("100000"), adv=ZERO)
        assert result.market_impact == ZERO

    def test_estimate_adv_none(self) -> None:
        m = TradeCostModel()
        result = m.estimate(Decimal("100000"), adv=None)
        assert result.market_impact == ZERO

    def test_custom_params(self) -> None:
        m = TradeCostModel(
            commission_bps=Decimal("20"),
            spread_bps=Decimal("10"),
            impact_coefficient=Decimal("0.5"),
        )
        result = m.estimate(Decimal("500000"), adv=Decimal("2000000"))

        # commission = 500000 * 20 / 10000 = 1000
        assert result.commission == Decimal("1000.00000000")
        assert result.spread_cost == Decimal("500.00000000")
        assert result.market_impact > ZERO

    def test_large_participation_high_impact(self) -> None:
        """Trading a large fraction of ADV → high market impact."""
        m = TradeCostModel(impact_coefficient=Decimal("0.1"))
        small = m.estimate(Decimal("10000"), adv=Decimal("1000000"))
        large = m.estimate(Decimal("500000"), adv=Decimal("1000000"))

        assert large.market_impact > small.market_impact
