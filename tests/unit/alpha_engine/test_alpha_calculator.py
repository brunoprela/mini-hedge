"""Unit tests for alpha engine calculators — what-if and portfolio optimization."""

from decimal import Decimal
from uuid import uuid4

import numpy as np
import pytest

from app.modules.alpha_engine.core.calculator import (
    optimize_portfolio,
    run_what_if,
)
from app.modules.alpha_engine.interfaces import (
    HypotheticalTrade,
    OptimizationObjective,
)

PORTFOLIO_ID = uuid4()


# ---------------------------------------------------------------------------
# What-if analysis
# ---------------------------------------------------------------------------


class TestWhatIf:
    def test_buy_increases_position(self):
        current = {"AAPL": (Decimal("100"), Decimal("15000"))}
        trades = [HypotheticalTrade("AAPL", "buy", Decimal("50"), Decimal("150"))]
        prices = {"AAPL": Decimal("150")}

        result = run_what_if(PORTFOLIO_ID, "buy more", current, trades, prices, nav=15000.0)
        aapl = next(p for p in result.positions if p.instrument_id == "AAPL")
        assert aapl.proposed_quantity == Decimal("150")

    def test_sell_decreases_position(self):
        current = {"AAPL": (Decimal("100"), Decimal("15000"))}
        trades = [HypotheticalTrade("AAPL", "sell", Decimal("30"), Decimal("150"))]
        prices = {"AAPL": Decimal("150")}

        result = run_what_if(PORTFOLIO_ID, "trim", current, trades, prices, nav=15000.0)
        aapl = next(p for p in result.positions if p.instrument_id == "AAPL")
        assert aapl.proposed_quantity == Decimal("70")

    def test_new_instrument_added(self):
        current = {"AAPL": (Decimal("100"), Decimal("15000"))}
        trades = [HypotheticalTrade("TSLA", "buy", Decimal("20"), Decimal("200"))]
        prices = {"AAPL": Decimal("150"), "TSLA": Decimal("200")}

        result = run_what_if(PORTFOLIO_ID, "add TSLA", current, trades, prices, nav=15000.0)
        ids = {p.instrument_id for p in result.positions}
        assert "TSLA" in ids

    def test_nav_change_correct(self):
        current = {"AAPL": (Decimal("100"), Decimal("15000"))}
        trades = [HypotheticalTrade("AAPL", "buy", Decimal("100"), Decimal("150"))]
        prices = {"AAPL": Decimal("150")}

        result = run_what_if(PORTFOLIO_ID, "double up", current, trades, prices, nav=15000.0)
        # 200 shares * $150 = $30,000 proposed NAV, change = +$15,000
        assert result.proposed_nav == Decimal("30000.0000")
        assert result.nav_change == Decimal("15000.0000")

    def test_proposed_weights_sum_to_one(self):
        current = {
            "AAPL": (Decimal("100"), Decimal("15000")),
            "JNJ": (Decimal("50"), Decimal("7500")),
        }
        trades = [HypotheticalTrade("AAPL", "buy", Decimal("10"), Decimal("150"))]
        prices = {"AAPL": Decimal("150"), "JNJ": Decimal("150")}

        result = run_what_if(PORTFOLIO_ID, "rebalance", current, trades, prices, nav=22500.0)
        total_weight = sum(float(p.proposed_weight) for p in result.positions)
        assert total_weight == pytest.approx(1.0, abs=1e-4)

    def test_zero_nav(self):
        current = {}
        trades = [HypotheticalTrade("AAPL", "buy", Decimal("100"), Decimal("150"))]
        prices = {"AAPL": Decimal("150")}

        result = run_what_if(PORTFOLIO_ID, "from scratch", current, trades, prices, nav=0.0)
        assert result.proposed_nav == Decimal("15000.0000")


# ---------------------------------------------------------------------------
# Portfolio optimization
# ---------------------------------------------------------------------------


class TestMinVariance:
    @pytest.fixture(autouse=True)
    def _setup(self):
        np.random.seed(42)
        n_days = 252
        # Stock A: low vol, Stock B: high vol — min-variance should overweight A
        self.returns = np.column_stack(
            [
                np.random.normal(0.0003, 0.01, n_days),  # A: 1% daily vol
                np.random.normal(0.0003, 0.03, n_days),  # B: 3% daily vol
            ]
        )
        self.ids = ["A", "B"]
        self.current_weights = {"A": 0.5, "B": 0.5}
        self.prices = {"A": 100.0, "B": 100.0}
        self.nav = 1_000_000.0

    def test_overweights_low_vol(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MIN_VARIANCE,
            self.current_weights,
            self.returns,
            self.ids,
            self.prices,
            self.nav,
        )
        w_a = next(w for w in result.weights if w.instrument_id == "A")
        w_b = next(w for w in result.weights if w.instrument_id == "B")
        assert float(w_a.target_weight) > float(w_b.target_weight)

    def test_weights_sum_to_one(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MIN_VARIANCE,
            self.current_weights,
            self.returns,
            self.ids,
            self.prices,
            self.nav,
        )
        total = sum(float(w.target_weight) for w in result.weights)
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_all_weights_non_negative(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MIN_VARIANCE,
            self.current_weights,
            self.returns,
            self.ids,
            self.prices,
            self.nav,
        )
        for w in result.weights:
            assert float(w.target_weight) >= 0


class TestMaxSharpe:
    @pytest.fixture(autouse=True)
    def _setup(self):
        np.random.seed(42)
        n_days = 252
        # Stock A: high return low vol, Stock B: low return high vol
        self.returns = np.column_stack(
            [
                np.random.normal(0.001, 0.01, n_days),  # A: good Sharpe
                np.random.normal(0.0001, 0.03, n_days),  # B: bad Sharpe
            ]
        )
        self.ids = ["A", "B"]
        self.current_weights = {"A": 0.5, "B": 0.5}
        self.prices = {"A": 100.0, "B": 100.0}
        self.nav = 1_000_000.0

    def test_overweights_high_sharpe(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MAX_SHARPE,
            self.current_weights,
            self.returns,
            self.ids,
            self.prices,
            self.nav,
        )
        w_a = next(w for w in result.weights if w.instrument_id == "A")
        w_b = next(w for w in result.weights if w.instrument_id == "B")
        assert float(w_a.target_weight) > float(w_b.target_weight)

    def test_sharpe_ratio_present(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MAX_SHARPE,
            self.current_weights,
            self.returns,
            self.ids,
            self.prices,
            self.nav,
        )
        assert result.sharpe_ratio is not None


class TestRiskParity:
    @pytest.fixture(autouse=True)
    def _setup(self):
        np.random.seed(42)
        n_days = 252
        # Stock A: 1% vol, Stock B: 3% vol → risk parity weights ≈ 3:1
        self.returns = np.column_stack(
            [
                np.random.normal(0, 0.01, n_days),
                np.random.normal(0, 0.03, n_days),
            ]
        )
        self.ids = ["A", "B"]
        self.current_weights = {"A": 0.5, "B": 0.5}
        self.prices = {"A": 100.0, "B": 100.0}
        self.nav = 1_000_000.0

    def test_weights_inversely_proportional_to_vol(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.RISK_PARITY,
            self.current_weights,
            self.returns,
            self.ids,
            self.prices,
            self.nav,
        )
        w_a = float(next(w for w in result.weights if w.instrument_id == "A").target_weight)
        w_b = float(next(w for w in result.weights if w.instrument_id == "B").target_weight)
        # A has 1/3 the vol of B, so should have ~3x the weight
        assert w_a / w_b == pytest.approx(3.0, rel=0.15)

    def test_weights_sum_to_one(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.RISK_PARITY,
            self.current_weights,
            self.returns,
            self.ids,
            self.prices,
            self.nav,
        )
        total = sum(float(w.target_weight) for w in result.weights)
        assert total == pytest.approx(1.0, abs=1e-4)


class TestOrderIntents:
    def test_material_delta_generates_intent(self):
        np.random.seed(42)
        returns = np.column_stack(
            [
                np.random.normal(0, 0.01, 252),
                np.random.normal(0, 0.03, 252),
            ]
        )
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MIN_VARIANCE,
            {"A": 0.5, "B": 0.5},
            returns,
            ["A", "B"],
            {"A": 100.0, "B": 100.0},
            1_000_000.0,
        )
        # Min-var will shift weights significantly from 50/50 → intents generated
        assert len(result.order_intents) > 0
        for intent in result.order_intents:
            assert intent.side in ("buy", "sell")
            assert intent.quantity > 0

    def test_no_instruments_returns_empty(self):
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MIN_VARIANCE,
            {},
            np.empty((0, 0)),
            [],
            {},
            1_000_000.0,
        )
        assert result.weights == []
        assert result.order_intents == []


class TestSingularCovariance:
    def test_fallback_to_equal_weight(self):
        """Singular covariance matrix → falls back to equal weight."""
        # Column B = 2 * Column A → perfectly collinear → singular covariance
        np.random.seed(42)
        col_a = np.random.normal(0, 0.01, 100)
        returns = np.column_stack([col_a, 2.0 * col_a])
        result = optimize_portfolio(
            PORTFOLIO_ID,
            OptimizationObjective.MIN_VARIANCE,
            {"A": 0.5, "B": 0.5},
            returns,
            ["A", "B"],
            {"A": 100.0, "B": 100.0},
            1_000_000.0,
        )
        for w in result.weights:
            assert float(w.target_weight) == pytest.approx(0.5, abs=0.01)
