"""Edge-case tests for risk calculator pure functions — nan/inf, currency factors, etc."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import numpy as np
import pytest

from app.modules.risk_engine.core.calculator import (
    _to_dec,
    calculate_factor_decomposition,
    calculate_historical_var,
    calculate_liquidity_profile,
    calculate_margin_requirements,
)
from app.modules.risk_engine.interfaces.var import VaRMethod

PORTFOLIO_ID = uuid4()

np.random.seed(99)
_N_DAYS = 252
_RETURNS_3 = np.column_stack(
    [
        np.random.normal(0.0004, 0.015, _N_DAYS),
        np.random.normal(0.0002, 0.025, _N_DAYS),
        np.random.normal(0.0003, 0.010, _N_DAYS),
    ]
)
_IDS_3 = ["AAPL", "TSLA", "JNJ"]


# ---------------------------------------------------------------------------
# _to_dec edge cases (nan, inf)
# ---------------------------------------------------------------------------


class TestToDec:
    def test_nan_returns_zero(self) -> None:
        assert _to_dec(float("nan")) == Decimal(0)

    def test_inf_returns_zero(self) -> None:
        assert _to_dec(float("inf")) == Decimal(0)

    def test_neg_inf_returns_zero(self) -> None:
        assert _to_dec(float("-inf")) == Decimal(0)

    def test_normal_value(self) -> None:
        result = _to_dec(0.1234)
        assert result == Decimal("0.1234")


# ---------------------------------------------------------------------------
# Factor decomposition with currency map
# ---------------------------------------------------------------------------


class TestFactorDecompositionCurrency:
    def test_currency_factors_included(self) -> None:
        """Non-base currency positions should produce currency factor exposures."""
        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        currency_map = {"AAPL": "USD", "TSLA": "EUR", "JNJ": "GBP"}
        weights = {"AAPL": 0.5, "TSLA": 0.3, "JNJ": 0.2}

        result = calculate_factor_decomposition(
            PORTFOLIO_ID,
            weights,
            _RETURNS_3,
            _IDS_3,
            sector_map,
            1_000_000.0,
            currency_map=currency_map,
            base_currency="USD",
        )

        factor_names = [fe.factor_name for fe in result.factor_exposures]
        # Should have currency factors for EUR and GBP
        assert "EUR" in factor_names
        assert "GBP" in factor_names

    def test_base_currency_not_in_factors(self) -> None:
        """Positions in base currency should not generate currency factor."""
        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "Healthcare"}
        currency_map = {"AAPL": "USD", "TSLA": "USD", "JNJ": "USD"}
        weights = {"AAPL": 0.5, "TSLA": 0.3, "JNJ": 0.2}

        result = calculate_factor_decomposition(
            PORTFOLIO_ID,
            weights,
            _RETURNS_3,
            _IDS_3,
            sector_map,
            1_000_000.0,
            currency_map=currency_map,
            base_currency="USD",
        )

        factor_names = [fe.factor_name for fe in result.factor_exposures]
        # Should only have Market, sectors, and Idiosyncratic — no currency
        non_standard = [
            n for n in factor_names
            if n not in ("Market", "Idiosyncratic", "Healthcare", "Technology")
        ]
        assert non_standard == []

    def test_sector_with_zero_variance_skipped(self) -> None:
        """Sector with identical returns (zero variance) should be skipped."""
        # Make all JNJ returns constant (zero variance)
        returns = _RETURNS_3.copy()
        returns[:, 2] = 0.0  # JNJ column all zeros

        sector_map = {"AAPL": "Technology", "TSLA": "Technology", "JNJ": "OnlySector"}
        weights = {"AAPL": 0.5, "TSLA": 0.3, "JNJ": 0.2}

        result = calculate_factor_decomposition(
            PORTFOLIO_ID,
            weights,
            returns,
            _IDS_3,
            sector_map,
            1_000_000.0,
        )

        factor_names = [fe.factor_name for fe in result.factor_exposures]
        # "OnlySector" should be skipped due to zero variance
        assert "OnlySector" not in factor_names


# ---------------------------------------------------------------------------
# Historical VaR — component VaR with very low portfolio vol
# ---------------------------------------------------------------------------


class TestComponentVarEdges:
    def test_near_zero_vol_returns_empty_contributions(self) -> None:
        """Near-zero portfolio volatility should return empty contributions."""
        # All returns near zero
        tiny_returns = np.zeros((_N_DAYS, 2)) + 1e-15
        weights = {"A": 0.5, "B": 0.5}
        result = calculate_historical_var(
            PORTFOLIO_ID, weights, tiny_returns, ["A", "B"]
        )
        # With zero returns, contributions list should be empty
        assert result.contributions == []


# ---------------------------------------------------------------------------
# Liquidity profile edge cases
# ---------------------------------------------------------------------------


class TestLiquidityProfileEdges:
    def test_1_week_bucket(self) -> None:
        """Position that takes 2-5 days should land in 1w bucket."""
        from datetime import UTC, datetime

        # ADV such that days_to_liquidate is ~2.5 days
        # mv=500, adv=1000, participation=0.2 => daily_capacity=200, days=2.5
        positions = [("INST", Decimal("500"), Decimal("1000"))]
        profile, details = calculate_liquidity_profile(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            total_nav=Decimal("500"),
            business_date=datetime.now(UTC),
        )
        assert details[0].liquidity_bucket == "1w"

    def test_1_month_bucket(self) -> None:
        """Position that takes 6-21 days should land in 1m bucket."""
        from datetime import UTC, datetime

        # mv=2000, adv=1000, participation=0.2 => daily_capacity=200, days=10
        positions = [("INST", Decimal("2000"), Decimal("1000"))]
        profile, details = calculate_liquidity_profile(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            total_nav=Decimal("2000"),
            business_date=datetime.now(UTC),
        )
        assert details[0].liquidity_bucket == "1m"

    def test_3_month_bucket(self) -> None:
        """Position that takes 22-63 days should land in 3m bucket."""
        from datetime import UTC, datetime

        # mv=10000, adv=1000, participation=0.2 => daily_capacity=200, days=50
        positions = [("INST", Decimal("10000"), Decimal("1000"))]
        profile, details = calculate_liquidity_profile(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            total_nav=Decimal("10000"),
            business_date=datetime.now(UTC),
        )
        assert details[0].liquidity_bucket == "3m"


# ---------------------------------------------------------------------------
# Margin requirements edge cases
# ---------------------------------------------------------------------------


class TestMarginRequirementsEdges:
    def test_different_asset_classes(self) -> None:
        """Different asset classes should get different margin rates."""
        from datetime import UTC, datetime

        positions = [
            ("EQ1", Decimal("1000000"), "equity"),
            ("BOND1", Decimal("1000000"), "fixed_income"),
            ("FX1", Decimal("1000000"), "fx"),
            ("OIL1", Decimal("1000000"), "commodity"),
        ]
        summary, pos_margins = calculate_margin_requirements(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            cash_balance=Decimal("5000000"),
            business_date=datetime.now(UTC),
        )

        rates = {m.instrument_id: m.margin_rate for m in pos_margins}
        assert rates["EQ1"] == Decimal("0.5")
        assert rates["BOND1"] == Decimal("0.1")
        assert rates["FX1"] == Decimal("0.03")
        assert rates["OIL1"] == Decimal("0.15")

    def test_unknown_asset_class_uses_default(self) -> None:
        from datetime import UTC, datetime

        positions = [("X", Decimal("1000000"), "crypto")]
        summary, pos_margins = calculate_margin_requirements(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            cash_balance=Decimal("1000000"),
            business_date=datetime.now(UTC),
        )
        # Default rate is 0.50
        assert pos_margins[0].margin_rate == Decimal("0.5")

    def test_margin_call_triggered(self) -> None:
        from datetime import UTC, datetime

        positions = [("EQ1", Decimal("10000000"), "equity")]
        # Cash well below margin requirement (equity: 50% of 10M = 5M initial)
        summary, _ = calculate_margin_requirements(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            cash_balance=Decimal("1000000"),
            business_date=datetime.now(UTC),
        )
        assert summary.margin_call_triggered is True
        assert summary.margin_excess_deficit < 0

    def test_zero_cash_margin_utilization(self) -> None:
        from datetime import UTC, datetime

        positions = [("EQ1", Decimal("1000000"), "equity")]
        summary, _ = calculate_margin_requirements(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            cash_balance=Decimal("0"),
            business_date=datetime.now(UTC),
        )
        # With zero cash, utilization should be 999
        assert summary.margin_utilization_pct == Decimal("999")

    def test_option_margin_rate(self) -> None:
        from datetime import UTC, datetime

        positions = [("OPT1", Decimal("500000"), "option")]
        summary, pos_margins = calculate_margin_requirements(
            portfolio_id=PORTFOLIO_ID,
            positions=positions,
            cash_balance=Decimal("1000000"),
            business_date=datetime.now(UTC),
        )
        assert pos_margins[0].margin_rate == Decimal("1.0")
