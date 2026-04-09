"""Unit tests for attribution calculators — Brinson-Fachler, risk-based, Carino linking."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import numpy as np
import pytest

from app.modules.attribution.core.calculator import (
    calculate_brinson_fachler,
    calculate_risk_based_attribution,
    link_multi_period,
)

PORTFOLIO_ID = uuid4()
START = date(2024, 1, 1)
END = date(2024, 1, 31)


# ---------------------------------------------------------------------------
# Brinson-Fachler
# ---------------------------------------------------------------------------


class TestBrinsonFachler:
    def test_active_return_equals_portfolio_minus_benchmark(self):
        """Active return = portfolio return - benchmark return."""
        portfolio_weights = {"AAPL": 0.6, "JNJ": 0.4}
        benchmark_weights = {"AAPL": 0.5, "JNJ": 0.5}
        portfolio_returns = {"AAPL": 0.10, "JNJ": 0.05}
        benchmark_returns = {"AAPL": 0.08, "JNJ": 0.04}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        result = calculate_brinson_fachler(
            PORTFOLIO_ID,
            START,
            END,
            portfolio_weights,
            benchmark_weights,
            portfolio_returns,
            benchmark_returns,
            sector_map,
        )
        # Portfolio return = 0.6*0.10 + 0.4*0.05 = 0.08
        # Benchmark return = 0.5*0.08 + 0.5*0.04 = 0.06
        # Active return = 0.02
        assert float(result.active_return) == pytest.approx(0.02, abs=1e-5)

    def test_effects_sum_to_active_return(self):
        """allocation + selection + interaction = active return."""
        portfolio_weights = {"AAPL": 0.7, "JNJ": 0.3}
        benchmark_weights = {"AAPL": 0.5, "JNJ": 0.5}
        portfolio_returns = {"AAPL": 0.12, "JNJ": 0.03}
        benchmark_returns = {"AAPL": 0.10, "JNJ": 0.02}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        result = calculate_brinson_fachler(
            PORTFOLIO_ID,
            START,
            END,
            portfolio_weights,
            benchmark_weights,
            portfolio_returns,
            benchmark_returns,
            sector_map,
        )
        total_effects = float(
            result.total_allocation + result.total_selection + result.total_interaction
        )
        assert total_effects == pytest.approx(float(result.active_return), abs=1e-5)

    def test_sectors_in_result(self):
        portfolio_weights = {"AAPL": 0.5, "JNJ": 0.5}
        benchmark_weights = {"AAPL": 0.5, "JNJ": 0.5}
        portfolio_returns = {"AAPL": 0.10, "JNJ": 0.05}
        benchmark_returns = {"AAPL": 0.10, "JNJ": 0.05}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        result = calculate_brinson_fachler(
            PORTFOLIO_ID,
            START,
            END,
            portfolio_weights,
            benchmark_weights,
            portfolio_returns,
            benchmark_returns,
            sector_map,
        )
        sector_names = [s.sector for s in result.sectors]
        assert "Technology" in sector_names
        assert "Healthcare" in sector_names

    def test_identical_portfolios_zero_active(self):
        """Same weights and returns → zero active return."""
        weights = {"AAPL": 0.5, "JNJ": 0.5}
        returns = {"AAPL": 0.10, "JNJ": 0.05}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        result = calculate_brinson_fachler(
            PORTFOLIO_ID, START, END, weights, weights, returns, returns, sector_map
        )
        assert float(result.active_return) == pytest.approx(0.0, abs=1e-6)

    def test_allocation_effect_direction(self):
        """Overweighting a winning sector produces positive allocation effect."""
        portfolio_weights = {"AAPL": 0.8, "JNJ": 0.2}
        benchmark_weights = {"AAPL": 0.5, "JNJ": 0.5}
        # Both sectors return the same in benchmark → isolate allocation effect
        portfolio_returns = {"AAPL": 0.10, "JNJ": 0.02}
        benchmark_returns = {"AAPL": 0.10, "JNJ": 0.02}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        result = calculate_brinson_fachler(
            PORTFOLIO_ID,
            START,
            END,
            portfolio_weights,
            benchmark_weights,
            portfolio_returns,
            benchmark_returns,
            sector_map,
        )
        # Overweight Tech (benchmark return 10% > overall benchmark 6%) → positive allocation
        assert result.total_allocation > 0


# ---------------------------------------------------------------------------
# Risk-based P&L attribution
# ---------------------------------------------------------------------------


class TestRiskBasedAttribution:
    @pytest.fixture(autouse=True)
    def _setup(self):
        np.random.seed(42)
        self.n_days = 100
        self.returns = np.column_stack(
            [
                np.random.normal(0.001, 0.02, self.n_days),
                np.random.normal(0.0005, 0.015, self.n_days),
                np.random.normal(0.0002, 0.01, self.n_days),
            ]
        )
        self.ids = ["AAPL", "TSLA", "JNJ"]
        self.weights = {"AAPL": 0.5, "TSLA": 0.3, "JNJ": 0.2}
        self.sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        self.nav = 1_000_000.0

    def test_systematic_plus_idiosyncratic_equals_total(self):
        result = calculate_risk_based_attribution(
            PORTFOLIO_ID,
            START,
            END,
            self.weights,
            self.returns,
            self.ids,
            self.sector_map,
            self.nav,
        )
        total = float(result.total_pnl)
        systematic = float(result.systematic_pnl)
        idiosyncratic = float(result.idiosyncratic_pnl)
        assert systematic + idiosyncratic == pytest.approx(total, abs=1.0)

    def test_factor_contributions_include_market(self):
        result = calculate_risk_based_attribution(
            PORTFOLIO_ID,
            START,
            END,
            self.weights,
            self.returns,
            self.ids,
            self.sector_map,
            self.nav,
        )
        factor_names = [fc.factor for fc in result.factor_contributions]
        assert "Market" in factor_names
        assert "Idiosyncratic" in factor_names

    def test_factor_contributions_include_sectors(self):
        result = calculate_risk_based_attribution(
            PORTFOLIO_ID,
            START,
            END,
            self.weights,
            self.returns,
            self.ids,
            self.sector_map,
            self.nav,
        )
        factor_names = [fc.factor for fc in result.factor_contributions]
        assert "Technology" in factor_names
        assert "Healthcare" in factor_names


# ---------------------------------------------------------------------------
# Carino multi-period linking
# ---------------------------------------------------------------------------


class TestCarinoLinking:
    def test_empty_periods(self):
        result = link_multi_period(PORTFOLIO_ID, START, END, [])
        assert result.cumulative_portfolio_return == Decimal(0)
        assert result.cumulative_active_return == Decimal(0)

    def test_single_period_passthrough(self):
        """Single period → cumulative equals single-period values."""
        weights = {"AAPL": 0.6, "JNJ": 0.4}
        bench_weights = {"AAPL": 0.5, "JNJ": 0.5}
        port_ret = {"AAPL": 0.10, "JNJ": 0.05}
        bench_ret = {"AAPL": 0.08, "JNJ": 0.04}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        bf = calculate_brinson_fachler(
            PORTFOLIO_ID, START, END, weights, bench_weights, port_ret, bench_ret, sector_map
        )
        result = link_multi_period(PORTFOLIO_ID, START, END, [bf])
        assert float(result.cumulative_portfolio_return) == pytest.approx(
            float(bf.portfolio_return), abs=1e-5
        )

    def test_multi_period_compounding(self):
        """Two periods compound geometrically."""
        weights = {"AAPL": 0.5, "JNJ": 0.5}
        bench_weights = {"AAPL": 0.5, "JNJ": 0.5}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        p1 = calculate_brinson_fachler(
            PORTFOLIO_ID,
            date(2024, 1, 1),
            date(2024, 1, 15),
            weights,
            bench_weights,
            {"AAPL": 0.10, "JNJ": 0.05},
            {"AAPL": 0.08, "JNJ": 0.04},
            sector_map,
        )
        p2 = calculate_brinson_fachler(
            PORTFOLIO_ID,
            date(2024, 1, 16),
            date(2024, 1, 31),
            weights,
            bench_weights,
            {"AAPL": 0.05, "JNJ": 0.03},
            {"AAPL": 0.04, "JNJ": 0.02},
            sector_map,
        )

        result = link_multi_period(PORTFOLIO_ID, START, END, [p1, p2])

        # Geometric compounding: (1+r1)*(1+r2) - 1
        expected_port = (1 + float(p1.portfolio_return)) * (1 + float(p2.portfolio_return)) - 1
        assert float(result.cumulative_portfolio_return) == pytest.approx(expected_port, abs=1e-5)

    def test_effects_sum_to_active_return_multi_period(self):
        """After linking, allocation + selection + interaction ≈ active return."""
        weights = {"AAPL": 0.7, "JNJ": 0.3}
        bench_weights = {"AAPL": 0.5, "JNJ": 0.5}
        sector_map = {"AAPL": "Technology", "JNJ": "Healthcare"}

        p1 = calculate_brinson_fachler(
            PORTFOLIO_ID,
            date(2024, 1, 1),
            date(2024, 1, 15),
            weights,
            bench_weights,
            {"AAPL": 0.10, "JNJ": 0.05},
            {"AAPL": 0.08, "JNJ": 0.04},
            sector_map,
        )
        p2 = calculate_brinson_fachler(
            PORTFOLIO_ID,
            date(2024, 1, 16),
            date(2024, 1, 31),
            weights,
            bench_weights,
            {"AAPL": 0.06, "JNJ": 0.02},
            {"AAPL": 0.05, "JNJ": 0.01},
            sector_map,
        )
        result = link_multi_period(PORTFOLIO_ID, START, END, [p1, p2])
        total_effects = float(
            result.cumulative_allocation
            + result.cumulative_selection
            + result.cumulative_interaction
        )
        assert total_effects == pytest.approx(float(result.cumulative_active_return), abs=2e-3)
