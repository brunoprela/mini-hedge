"""Unit tests for risk engine calculators — pure functions, no I/O."""

from decimal import Decimal
from uuid import uuid4

import numpy as np
import pytest

from app.modules.risk_engine.core.calculator import (
    calculate_factor_decomposition,
    calculate_historical_var,
    calculate_parametric_var,
    run_stress_test,
)
from app.modules.risk_engine.interfaces.stress import StressScenario, StressScenarioType
from app.modules.risk_engine.interfaces.var import VaRMethod

PORTFOLIO_ID = uuid4()

# ---------------------------------------------------------------------------
# Deterministic returns for reproducible tests
# ---------------------------------------------------------------------------

np.random.seed(42)
# 252 days, 3 instruments with known characteristics
_N_DAYS = 252
_RETURNS = np.column_stack(
    [
        np.random.normal(0.0004, 0.015, _N_DAYS),  # low-vol stock A
        np.random.normal(0.0002, 0.025, _N_DAYS),  # high-vol stock B
        np.random.normal(0.0003, 0.010, _N_DAYS),  # very-low-vol stock C
    ]
)
_IDS = ["AAPL", "TSLA", "JNJ"]
_WEIGHTS = {"AAPL": 0.5, "TSLA": 0.3, "JNJ": 0.2}
_NAV = 1_000_000.0


# ---------------------------------------------------------------------------
# Historical VaR
# ---------------------------------------------------------------------------


class TestHistoricalVaR:
    def test_returns_correct_method(self):
        result = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert result.method == VaRMethod.HISTORICAL

    def test_var_is_positive(self):
        result = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert result.var_amount > 0
        assert result.var_pct > 0

    def test_expected_shortfall_exceeds_var(self):
        result = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert result.expected_shortfall >= result.var_amount

    def test_confidence_level_preserved(self):
        result = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, confidence=0.99)
        assert result.confidence_level == 0.99

    def test_higher_confidence_gives_higher_var(self):
        var_95 = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, confidence=0.95)
        var_99 = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, confidence=0.99)
        assert var_99.var_amount > var_95.var_amount

    def test_horizon_scaling(self):
        var_1d = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, horizon_days=1)
        var_10d = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, horizon_days=10)
        assert var_10d.var_amount > var_1d.var_amount
        assert var_10d.horizon_days == 10

    def test_component_var_contributions_exist(self):
        result = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert len(result.contributions) > 0
        for c in result.contributions:
            assert c.instrument_id in _IDS

    def test_zero_weight_instrument_excluded(self):
        weights = {"AAPL": 1.0, "TSLA": 0.0, "JNJ": 0.0}
        result = calculate_historical_var(PORTFOLIO_ID, weights, _RETURNS, _IDS)
        contrib_ids = {c.instrument_id for c in result.contributions}
        assert "AAPL" in contrib_ids
        assert "TSLA" not in contrib_ids

    def test_single_instrument(self):
        returns_1 = _RETURNS[:, :1]
        result = calculate_historical_var(PORTFOLIO_ID, {"AAPL": 1.0}, returns_1, ["AAPL"])
        assert result.var_amount > 0

    def test_var_matches_percentile(self):
        """Verify VaR is the negative 5th percentile of portfolio returns."""
        w = np.array([_WEIGHTS.get(iid, 0.0) for iid in _IDS])
        port_returns = _RETURNS @ w
        expected_var_pct = float(-np.percentile(port_returns, 5))
        result = calculate_historical_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert float(result.var_pct) == pytest.approx(expected_var_pct, abs=1e-4)


# ---------------------------------------------------------------------------
# Parametric VaR
# ---------------------------------------------------------------------------


class TestParametricVaR:
    def test_returns_correct_method(self):
        result = calculate_parametric_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert result.method == VaRMethod.PARAMETRIC

    def test_var_is_positive(self):
        result = calculate_parametric_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert result.var_amount > 0

    def test_expected_shortfall_exceeds_var(self):
        result = calculate_parametric_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS)
        assert result.expected_shortfall >= result.var_amount

    def test_higher_confidence_gives_higher_var(self):
        var_95 = calculate_parametric_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, confidence=0.95)
        var_99 = calculate_parametric_var(PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, confidence=0.99)
        assert var_99.var_amount > var_95.var_amount

    def test_single_instrument_scalar_cov(self):
        """Covariance of a single instrument is a scalar — must handle ndim=0."""
        returns_1 = _RETURNS[:, :1]
        result = calculate_parametric_var(PORTFOLIO_ID, {"AAPL": 1.0}, returns_1, ["AAPL"])
        assert result.var_amount > 0


# ---------------------------------------------------------------------------
# Stress testing
# ---------------------------------------------------------------------------


class TestStressTest:
    def test_uniform_market_shock(self):
        positions = {
            "AAPL": (Decimal("500000"), "Technology"),
            "JNJ": (Decimal("300000"), "Healthcare"),
        }
        scenario = StressScenario(
            name="Crash",
            scenario_type=StressScenarioType.PREDEFINED,
            shocks={"market": -0.20},
        )
        result = run_stress_test(PORTFOLIO_ID, scenario, positions, nav=800_000.0)
        # -20% of 800k = -160k
        assert result.total_pnl_impact == Decimal("-160000.0000")
        assert len(result.position_impacts) == 2

    def test_sector_specific_shock(self):
        positions = {
            "AAPL": (Decimal("500000"), "Technology"),
            "JNJ": (Decimal("300000"), "Healthcare"),
        }
        scenario = StressScenario(
            name="Tech selloff",
            scenario_type=StressScenarioType.CUSTOM,
            shocks={"Technology": -0.30, "market": -0.10},
        )
        result = run_stress_test(PORTFOLIO_ID, scenario, positions, nav=800_000.0)
        # AAPL: -30% of 500k = -150k, JNJ: -10% of 300k = -30k
        assert result.total_pnl_impact == Decimal("-180000.0000")

    def test_instrument_specific_shock_overrides_sector(self):
        positions = {
            "AAPL": (Decimal("500000"), "Technology"),
        }
        scenario = StressScenario(
            name="AAPL specific",
            scenario_type=StressScenarioType.CUSTOM,
            shocks={"AAPL": -0.50, "Technology": -0.10, "market": -0.05},
        )
        result = run_stress_test(PORTFOLIO_ID, scenario, positions, nav=500_000.0)
        # Instrument-level -50% overrides sector -10%
        assert result.total_pnl_impact == Decimal("-250000.0000")

    def test_positive_shock(self):
        positions = {"XOM": (Decimal("400000"), "Energy")}
        scenario = StressScenario(
            name="Energy rally",
            scenario_type=StressScenarioType.CUSTOM,
            shocks={"Energy": 0.25},
        )
        result = run_stress_test(PORTFOLIO_ID, scenario, positions, nav=400_000.0)
        assert result.total_pnl_impact == Decimal("100000.0000")

    def test_no_matching_shock_defaults_to_zero(self):
        positions = {"AAPL": (Decimal("100000"), "Technology")}
        scenario = StressScenario(
            name="Empty",
            scenario_type=StressScenarioType.CUSTOM,
            shocks={},
        )
        result = run_stress_test(PORTFOLIO_ID, scenario, positions, nav=100_000.0)
        assert result.total_pnl_impact == Decimal("0.0000")

    def test_pct_change_relative_to_nav(self):
        positions = {"AAPL": (Decimal("500000"), "Technology")}
        scenario = StressScenario(
            name="Crash",
            scenario_type=StressScenarioType.PREDEFINED,
            shocks={"market": -0.20},
        )
        result = run_stress_test(PORTFOLIO_ID, scenario, positions, nav=1_000_000.0)
        # -100k impact on 1M NAV = -10%
        assert result.total_pct_change == Decimal("-0.1000")


# ---------------------------------------------------------------------------
# Factor decomposition
# ---------------------------------------------------------------------------


class TestFactorDecomposition:
    def test_systematic_plus_idiosyncratic_equals_total(self):
        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        result = calculate_factor_decomposition(
            PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, sector_map, _NAV
        )
        # Systematic + idiosyncratic should approximately equal total risk
        # (small rounding errors expected)
        total = float(result.total_risk)
        sys_risk = float(result.systematic_risk)
        idio_risk = float(result.idiosyncratic_risk)
        assert total > 0
        assert sys_risk >= 0
        assert idio_risk >= 0

    def test_factor_exposures_contain_market_and_idiosyncratic(self):
        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        result = calculate_factor_decomposition(
            PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, sector_map, _NAV
        )
        factor_names = [fe.factor_name for fe in result.factor_exposures]
        assert "Market" in factor_names
        assert "Idiosyncratic" in factor_names

    def test_sector_exposures_present(self):
        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        result = calculate_factor_decomposition(
            PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, sector_map, _NAV
        )
        sector_names = [
            fe.factor_name
            for fe in result.factor_exposures
            if fe.factor_name not in ("Market", "Idiosyncratic")
        ]
        assert "Technology" in sector_names
        assert "Healthcare" in sector_names

    def test_zero_variance_portfolio(self):
        """All-zero returns should produce zero risk."""
        zero_returns = np.zeros((_N_DAYS, 3))
        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        result = calculate_factor_decomposition(
            PORTFOLIO_ID, _WEIGHTS, zero_returns, _IDS, sector_map, _NAV
        )
        assert result.total_risk == Decimal(0)
        assert result.systematic_risk == Decimal(0)
        assert result.idiosyncratic_risk == Decimal(0)

    def test_systematic_pct_between_zero_and_one(self):
        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        result = calculate_factor_decomposition(
            PORTFOLIO_ID, _WEIGHTS, _RETURNS, _IDS, sector_map, _NAV
        )
        assert Decimal(0) <= result.systematic_pct <= Decimal(2)
