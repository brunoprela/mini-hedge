"""Unit tests for FX hedging calculator — pure functions, no I/O."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.fx_hedging.core.calculator import (
    calculate_carry_pnl,
    calculate_forward_rate,
    calculate_roll_cost,
    identify_expiring_forwards,
    mark_to_market_forward,
    recommend_hedges,
)


class TestCalculateForwardRate:
    def test_positive_rate_differential(self) -> None:
        """Higher domestic rate → forward > spot (forward premium)."""
        result = calculate_forward_rate(
            spot=Decimal("1.2500"),
            domestic_rate=Decimal("0.05"),
            foreign_rate=Decimal("0.03"),
            tenor_days=90,
        )
        assert result.forward > result.spot
        assert result.forward_points > Decimal(0)
        assert result.tenor_days == 90

    def test_negative_rate_differential(self) -> None:
        """Higher foreign rate → forward < spot (forward discount)."""
        result = calculate_forward_rate(
            spot=Decimal("1.2500"),
            domestic_rate=Decimal("0.02"),
            foreign_rate=Decimal("0.05"),
            tenor_days=90,
        )
        assert result.forward < result.spot
        assert result.forward_points < Decimal(0)

    def test_equal_rates_forward_equals_spot(self) -> None:
        result = calculate_forward_rate(
            spot=Decimal("1.2500"),
            domestic_rate=Decimal("0.04"),
            foreign_rate=Decimal("0.04"),
            tenor_days=90,
        )
        assert result.forward == result.spot
        assert result.forward_points == Decimal(0)

    def test_zero_tenor(self) -> None:
        result = calculate_forward_rate(
            spot=Decimal("1.2500"),
            domestic_rate=Decimal("0.05"),
            foreign_rate=Decimal("0.03"),
            tenor_days=0,
        )
        assert result.forward == result.spot

    def test_one_year_tenor(self) -> None:
        result = calculate_forward_rate(
            spot=Decimal("1.2500"),
            domestic_rate=Decimal("0.05"),
            foreign_rate=Decimal("0.03"),
            tenor_days=360,
        )
        # F = 1.25 * (1 + 0.05) / (1 + 0.03) = 1.25 * 1.05/1.03 ≈ 1.27427
        assert result.forward == pytest.approx(Decimal("1.274272"), abs=Decimal("0.001"))


class TestMarkToMarketForward:
    def test_buy_in_the_money(self) -> None:
        """Spot moved up → buy forward is in the money."""
        result = mark_to_market_forward(
            contract_rate=Decimal("1.2500"),
            contract_notional=Decimal("1000000"),
            contract_direction="buy",
            current_spot=Decimal("1.2800"),
            domestic_rate=Decimal("0.04"),
            foreign_rate=Decimal("0.03"),
            remaining_days=30,
            quote_currency="EUR",
        )
        assert result.mtm_value > Decimal(0)
        assert result.notional == Decimal("1000000")

    def test_sell_in_the_money(self) -> None:
        """Spot moved down → sell forward is in the money."""
        result = mark_to_market_forward(
            contract_rate=Decimal("1.2500"),
            contract_notional=Decimal("1000000"),
            contract_direction="sell",
            current_spot=Decimal("1.2200"),
            domestic_rate=Decimal("0.04"),
            foreign_rate=Decimal("0.03"),
            remaining_days=30,
            quote_currency="EUR",
        )
        assert result.mtm_value > Decimal(0)

    def test_buy_out_of_money(self) -> None:
        """Spot moved down → buy forward is out of the money."""
        result = mark_to_market_forward(
            contract_rate=Decimal("1.2500"),
            contract_notional=Decimal("1000000"),
            contract_direction="buy",
            current_spot=Decimal("1.2200"),
            domestic_rate=Decimal("0.04"),
            foreign_rate=Decimal("0.03"),
            remaining_days=30,
            quote_currency="EUR",
        )
        assert result.mtm_value < Decimal(0)


class TestCalculateCarryPnl:
    def test_spot_carry_decomposition_sums(self) -> None:
        result = calculate_carry_pnl(
            entry_spot=Decimal("1.2500"),
            current_spot=Decimal("1.2700"),
            contract_rate=Decimal("1.2520"),
            current_forward=Decimal("1.2720"),
            notional=Decimal("1000000"),
            direction="buy",
        )
        assert result.total_pnl == result.spot_pnl + result.carry_pnl

    def test_sell_direction_reverses_sign(self) -> None:
        buy = calculate_carry_pnl(
            entry_spot=Decimal("1.2500"),
            current_spot=Decimal("1.2700"),
            contract_rate=Decimal("1.2520"),
            current_forward=Decimal("1.2720"),
            notional=Decimal("1000000"),
            direction="buy",
        )
        sell = calculate_carry_pnl(
            entry_spot=Decimal("1.2500"),
            current_spot=Decimal("1.2700"),
            contract_rate=Decimal("1.2520"),
            current_forward=Decimal("1.2720"),
            notional=Decimal("1000000"),
            direction="sell",
        )
        assert buy.total_pnl == -sell.total_pnl


class TestRecommendHedges:
    def test_positive_exposure_generates_sell_recommendation(self) -> None:
        recs = recommend_hedges(
            currency_exposures={"EUR": Decimal("5000000"), "USD": Decimal("0")},
            base_currency="USD",
            spots={"EUR": Decimal("1.0800")},
            domestic_rate=Decimal("0.05"),
            foreign_rates={"EUR": Decimal("0.04")},
            hedge_ratio=Decimal("1.0"),
            tenor_days=30,
        )
        assert len(recs) == 1
        assert recs[0].direction == "sell"
        assert recs[0].notional == Decimal("5000000.00")
        assert recs[0].currency_pair == "USD/EUR"

    def test_negative_exposure_generates_buy_recommendation(self) -> None:
        recs = recommend_hedges(
            currency_exposures={"GBP": Decimal("-3000000")},
            base_currency="USD",
            spots={"GBP": Decimal("1.2600")},
            domestic_rate=Decimal("0.05"),
            foreign_rates={"GBP": Decimal("0.04")},
        )
        assert len(recs) == 1
        assert recs[0].direction == "buy"

    def test_base_currency_exposure_skipped(self) -> None:
        recs = recommend_hedges(
            currency_exposures={"USD": Decimal("10000000")},
            base_currency="USD",
            spots={},
            domestic_rate=Decimal("0.05"),
            foreign_rates={},
        )
        assert recs == []

    def test_zero_exposure_skipped(self) -> None:
        recs = recommend_hedges(
            currency_exposures={"EUR": Decimal("0")},
            base_currency="USD",
            spots={"EUR": Decimal("1.0800")},
            domestic_rate=Decimal("0.05"),
            foreign_rates={"EUR": Decimal("0.04")},
        )
        assert recs == []

    def test_partial_hedge_ratio(self) -> None:
        recs = recommend_hedges(
            currency_exposures={"EUR": Decimal("10000000")},
            base_currency="USD",
            spots={"EUR": Decimal("1.0800")},
            domestic_rate=Decimal("0.05"),
            foreign_rates={"EUR": Decimal("0.04")},
            hedge_ratio=Decimal("0.50"),
        )
        assert len(recs) == 1
        assert recs[0].notional == Decimal("5000000.00")
        assert recs[0].hedge_ratio == Decimal("0.50")


class TestIdentifyExpiringForwards:
    def test_finds_expiring_within_window(self) -> None:
        maturities = [
            ("fwd-1", date(2026, 4, 14)),
            ("fwd-2", date(2026, 4, 20)),
            ("fwd-3", date(2026, 5, 1)),
        ]
        result = identify_expiring_forwards(maturities, date(2026, 4, 12), days_ahead=5)
        assert len(result) == 1
        assert result[0][0] == "fwd-1"
        assert result[0][2] == 2  # days remaining

    def test_already_expired_returns_zero_days(self) -> None:
        maturities = [("fwd-1", date(2026, 4, 10))]
        result = identify_expiring_forwards(maturities, date(2026, 4, 12), days_ahead=5)
        assert len(result) == 1
        assert result[0][2] == 0  # clamped to 0

    def test_no_expiring(self) -> None:
        maturities = [("fwd-1", date(2026, 5, 1))]
        result = identify_expiring_forwards(maturities, date(2026, 4, 12), days_ahead=5)
        assert result == []

    def test_sorted_by_days_remaining(self) -> None:
        maturities = [
            ("fwd-2", date(2026, 4, 16)),
            ("fwd-1", date(2026, 4, 13)),
        ]
        result = identify_expiring_forwards(maturities, date(2026, 4, 12), days_ahead=5)
        assert result[0][0] == "fwd-1"
        assert result[1][0] == "fwd-2"


class TestCalculateRollCost:
    def test_produces_valid_cost(self) -> None:
        result = calculate_roll_cost(
            contract_rate=Decimal("1.2520"),
            contract_notional=Decimal("1000000"),
            direction="buy",
            current_spot=Decimal("1.2700"),
            domestic_rate=Decimal("0.05"),
            foreign_rate=Decimal("0.03"),
            remaining_days=5,
            new_tenor_days=30,
        )
        assert result.old_forward is not None
        assert result.new_forward is not None
        assert result.cost_bps >= Decimal(0)
