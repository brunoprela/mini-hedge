"""Unit tests for factor engine — pure quant factor computations."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.modules.quant_research.core.factor_engine import (
    _safe_return,
    _z_scores,
    compute_factor_correlation,
    compute_factor_returns,
    compute_momentum_factor,
    compute_quality_factor,
    compute_size_factor,
    compute_value_factor,
    compute_volatility_factor,
    decompose_portfolio,
)

ZERO = Decimal(0)


def _make_price_series(
    start_price: float = 100.0,
    days: int = 300,
    daily_return: float = 0.001,
) -> list[tuple[date, Decimal]]:
    """Generate a synthetic price series."""
    series = []
    price = start_price
    start = date(2024, 1, 1)
    for i in range(days):
        series.append((start + timedelta(days=i), Decimal(str(round(price, 4)))))
        price *= 1 + daily_return
    return series


class TestHelpers:
    def test_safe_return_normal(self) -> None:
        assert _safe_return(Decimal("110"), Decimal("100")) == Decimal("0.1")

    def test_safe_return_zero_previous(self) -> None:
        assert _safe_return(Decimal("100"), ZERO) == ZERO

    def test_z_scores_basic(self) -> None:
        values = {"A": Decimal("10"), "B": Decimal("20"), "C": Decimal("30")}
        z = _z_scores(values)
        assert len(z) == 3
        # Mean=20, so A is negative, B is ~0, C is positive
        assert z["A"] < ZERO
        assert z["C"] > ZERO

    def test_z_scores_single_value(self) -> None:
        z = _z_scores({"A": Decimal("10")})
        assert z["A"] == ZERO

    def test_z_scores_identical_values(self) -> None:
        z = _z_scores({"A": Decimal("10"), "B": Decimal("10")})
        assert z["A"] == ZERO
        assert z["B"] == ZERO


class TestMomentumFactor:
    def test_positive_momentum(self) -> None:
        prices = {
            "WINNER": _make_price_series(100, 300, 0.002),
            "LOSER": _make_price_series(100, 300, -0.001),
        }
        factors = compute_momentum_factor(prices, lookback=252, skip_recent=21)
        assert "WINNER" in factors
        assert "LOSER" in factors
        assert factors["WINNER"] > factors["LOSER"]

    def test_insufficient_data_excluded(self) -> None:
        prices = {"SHORT": _make_price_series(100, 50, 0.001)}
        factors = compute_momentum_factor(prices, lookback=252)
        assert factors == {}


class TestValueFactor:
    def test_basic_value(self) -> None:
        fundamentals = {
            "CHEAP": {"price": Decimal("50"), "earnings": Decimal("10"), "book_value": Decimal("40"), "sales": Decimal("100")},
            "EXPENSIVE": {"price": Decimal("200"), "earnings": Decimal("5"), "book_value": Decimal("20"), "sales": Decimal("50")},
        }
        factors = compute_value_factor(fundamentals)
        assert factors["CHEAP"] > factors["EXPENSIVE"]

    def test_zero_price_excluded(self) -> None:
        fundamentals = {"ZERO": {"price": ZERO, "earnings": Decimal("10"), "book_value": Decimal("40")}}
        assert compute_value_factor(fundamentals) == {}


class TestSizeFactor:
    def test_small_cap_higher_exposure(self) -> None:
        market_caps = {
            "SMALL": Decimal("1000000"),
            "LARGE": Decimal("100000000000"),
        }
        factors = compute_size_factor(market_caps)
        # Small-cap factor inverts: smaller = higher exposure
        assert factors["SMALL"] > factors["LARGE"]

    def test_zero_mcap_excluded(self) -> None:
        factors = compute_size_factor({"ZERO": ZERO})
        assert factors == {}


class TestQualityFactor:
    def test_high_quality_scores_higher(self) -> None:
        fundamentals = {
            "QUALITY": {"equity": Decimal("100"), "earnings": Decimal("20"), "debt": Decimal("10"), "earnings_stability": Decimal("0.9")},
            "JUNK": {"equity": Decimal("100"), "earnings": Decimal("5"), "debt": Decimal("90"), "earnings_stability": Decimal("0.1")},
        }
        factors = compute_quality_factor(fundamentals)
        assert factors["QUALITY"] > factors["JUNK"]


class TestVolatilityFactor:
    def test_low_vol_higher_exposure(self) -> None:
        # Steady price series = low vol
        steady = _make_price_series(100, 100, 0.001)
        # Volatile series
        volatile = []
        start = date(2024, 1, 1)
        price = 100.0
        for i in range(100):
            sign = 1 if i % 2 == 0 else -1
            price *= 1 + sign * 0.03
            volatile.append((start + timedelta(days=i), Decimal(str(round(price, 4)))))

        prices = {"STEADY": steady, "VOLATILE": volatile}
        factors = compute_volatility_factor(prices, window=63)
        assert factors["STEADY"] > factors["VOLATILE"]

    def test_insufficient_data_excluded(self) -> None:
        prices = {"SHORT": _make_price_series(100, 10, 0.001)}
        assert compute_volatility_factor(prices, window=63) == {}


class TestFactorReturns:
    def test_long_short_return(self) -> None:
        exposures = {"A": Decimal("2"), "B": Decimal("1"), "C": Decimal("-1"), "D": Decimal("-2"), "E": Decimal("0")}
        returns = {"A": Decimal("0.05"), "B": Decimal("0.03"), "C": Decimal("-0.02"), "D": Decimal("-0.04"), "E": Decimal("0")}
        factor_return = compute_factor_returns(exposures, returns)
        # Long top quintile (A), short bottom quintile (D)
        assert factor_return > ZERO

    def test_empty_exposures(self) -> None:
        assert compute_factor_returns({}, {}) == ZERO


class TestFactorCorrelation:
    def test_self_correlation_is_one(self) -> None:
        factor_returns = {
            "momentum": [Decimal("0.01"), Decimal("-0.02"), Decimal("0.03")],
            "value": [Decimal("0.02"), Decimal("0.01"), Decimal("-0.01")],
        }
        matrix = compute_factor_correlation(factor_returns)
        assert matrix["momentum"]["momentum"] == 1.0
        assert matrix["value"]["value"] == 1.0

    def test_correlation_between_factors(self) -> None:
        factor_returns = {
            "A": [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")],
            "B": [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")],  # perfectly correlated
        }
        matrix = compute_factor_correlation(factor_returns)
        assert abs(matrix["A"]["B"] - 1.0) < 0.0001

    def test_insufficient_data(self) -> None:
        factor_returns = {"A": [Decimal("0.01")], "B": [Decimal("0.02")]}
        matrix = compute_factor_correlation(factor_returns)
        assert matrix["A"]["B"] == 0.0


class TestDecomposePortfolio:
    def test_basic_decomposition(self) -> None:
        weights = {"AAPL": Decimal("0.5"), "MSFT": Decimal("0.3"), "GOOG": Decimal("0.2")}
        factor_exposures = {
            "momentum": {"AAPL": Decimal("1.2"), "MSFT": Decimal("0.5"), "GOOG": Decimal("-0.3")},
            "value": {"AAPL": Decimal("-0.5"), "MSFT": Decimal("1.0"), "GOOG": Decimal("0.8")},
        }
        contributions, residual = decompose_portfolio(weights, factor_exposures)
        assert "momentum" in contributions
        assert "value" in contributions
        assert residual >= ZERO

    def test_empty_portfolio(self) -> None:
        contributions, residual = decompose_portfolio({}, {"momentum": {"AAPL": Decimal("1")}})
        assert all(v == ZERO for v in contributions.values())
