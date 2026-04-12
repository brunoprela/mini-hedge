"""Unit tests for BacktestEngine — signal functions, metrics, and engine run."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.modules.backtesting.core.engine import (
    BacktestEngine,
    _compute_calmar,
    _compute_max_drawdown,
    _compute_monthly_returns,
    _compute_profit_factor,
    _compute_returns,
    _compute_sharpe,
    _compute_sortino,
    _compute_volatility,
    _compute_win_rate,
    _should_rebalance,
    equal_weight_signal,
    mean_reversion_signal,
    momentum_signal,
)
from app.modules.backtesting.interfaces import (
    BacktestConfig,
    BacktestTrade,
    EquityCurvePoint,
    RebalanceFrequency,
)

ZERO = Decimal(0)


def _make_curve(values: list[tuple[date, Decimal]]) -> list[EquityCurvePoint]:
    peak = ZERO
    pts = []
    for d, v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak != ZERO else ZERO
        pts.append(EquityCurvePoint(date=d, portfolio_value=v, benchmark_value=None, drawdown=dd))
    return pts


def _make_price_data(
    instruments: list[str],
    days: int = 30,
    start_price: float = 100.0,
    daily_change: float = 1.0,
) -> dict[str, list[tuple[date, Decimal]]]:
    start = date(2025, 1, 1)
    data: dict[str, list[tuple[date, Decimal]]] = {}
    for inst in instruments:
        series = []
        price = start_price
        for i in range(days):
            d = start + timedelta(days=i)
            if d.weekday() < 5:
                series.append((d, Decimal(str(round(price, 2)))))
            price += daily_change
        data[inst] = series
    return data


class TestSignalFunctions:
    def test_equal_weight(self) -> None:
        prices = {"AAPL": Decimal("150"), "MSFT": Decimal("300")}
        weights = equal_weight_signal(date(2025, 1, 1), prices, {})
        assert len(weights) == 2
        assert weights["AAPL"] == Decimal("0.5")
        assert weights["MSFT"] == Decimal("0.5")

    def test_equal_weight_empty(self) -> None:
        assert equal_weight_signal(date(2025, 1, 1), {}, {}) == {}

    def test_momentum_no_history(self) -> None:
        prices = {"AAPL": Decimal("150"), "MSFT": Decimal("300")}
        weights = momentum_signal(date(2025, 1, 1), prices, {})
        # Falls back to equal weight
        assert len(weights) == 2

    def test_momentum_with_history(self) -> None:
        start = date(2024, 1, 1)
        history = {
            "WINNER": [(start + timedelta(days=i), Decimal(str(100 + i))) for i in range(30)],
            "LOSER": [(start + timedelta(days=i), Decimal(str(100 - i * 0.5))) for i in range(30)],
        }
        current = start + timedelta(days=29)
        prices = {"WINNER": Decimal("129"), "LOSER": Decimal("85.5")}
        weights = momentum_signal(current, prices, {}, lookback=20, _price_history=history)
        assert "WINNER" in weights

    def test_mean_reversion_no_history(self) -> None:
        prices = {"AAPL": Decimal("150")}
        weights = mean_reversion_signal(date(2025, 1, 1), prices, {})
        assert len(weights) == 1

    def test_mean_reversion_with_history(self) -> None:
        start = date(2024, 1, 1)
        history = {
            "WINNER": [(start + timedelta(days=i), Decimal(str(100 + i))) for i in range(30)],
            "LOSER": [(start + timedelta(days=i), Decimal(str(100 - i * 0.5))) for i in range(30)],
        }
        current = start + timedelta(days=29)
        prices = {"WINNER": Decimal("129"), "LOSER": Decimal("85.5")}
        weights = mean_reversion_signal(current, prices, {}, lookback=20, _price_history=history)
        # Mean reversion favors losers
        assert "LOSER" in weights


class TestMetrics:
    def test_compute_returns(self) -> None:
        curve = _make_curve([
            (date(2025, 1, 1), Decimal("1000")),
            (date(2025, 1, 2), Decimal("1010")),
            (date(2025, 1, 3), Decimal("1005")),
        ])
        returns = _compute_returns(curve)
        assert len(returns) == 2
        assert returns[0] == Decimal("10") / Decimal("1000")

    def test_compute_returns_zero_prev(self) -> None:
        curve = _make_curve([
            (date(2025, 1, 1), ZERO),
            (date(2025, 1, 2), Decimal("100")),
        ])
        returns = _compute_returns(curve)
        assert returns[0] == ZERO

    def test_compute_sharpe(self) -> None:
        returns = [Decimal("0.01")] * 30
        sharpe = _compute_sharpe(returns)
        assert isinstance(sharpe, Decimal)

    def test_compute_sharpe_insufficient(self) -> None:
        assert _compute_sharpe([Decimal("0.01")]) == ZERO

    def test_compute_sharpe_zero_std(self) -> None:
        # All returns equal to daily risk-free → zero excess std
        daily_rf = Decimal("0.04") / Decimal("252")
        returns = [daily_rf] * 10
        assert _compute_sharpe(returns) == ZERO

    def test_compute_sortino(self) -> None:
        returns = [Decimal("0.01"), Decimal("-0.02"), Decimal("0.03"), Decimal("-0.01")]
        sortino = _compute_sortino(returns)
        assert isinstance(sortino, Decimal)

    def test_compute_sortino_no_downside(self) -> None:
        returns = [Decimal("0.01"), Decimal("0.02")]
        # Excess returns are positive only (for high risk-free, some may be negative)
        sortino = _compute_sortino(returns, risk_free_rate=0.0)
        # No downside returns → returns ZERO
        assert sortino == ZERO

    def test_compute_max_drawdown(self) -> None:
        curve = _make_curve([
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("90")),
            (date(2025, 1, 3), Decimal("110")),
        ])
        dd = _compute_max_drawdown(curve)
        assert dd == Decimal("10") / Decimal("100")

    def test_compute_max_drawdown_empty(self) -> None:
        assert _compute_max_drawdown([]) == ZERO

    def test_compute_calmar(self) -> None:
        assert _compute_calmar(Decimal("0.10"), Decimal("0.05")) == Decimal("2")

    def test_compute_calmar_zero_dd(self) -> None:
        assert _compute_calmar(Decimal("0.10"), ZERO) == ZERO

    def test_compute_volatility(self) -> None:
        returns = [Decimal("0.01"), Decimal("-0.02"), Decimal("0.03")]
        vol = _compute_volatility(returns)
        assert vol > ZERO

    def test_compute_volatility_insufficient(self) -> None:
        assert _compute_volatility([Decimal("0.01")]) == ZERO

    def test_compute_win_rate(self) -> None:
        trades = [
            BacktestTrade(date=date(2025, 1, 1), instrument_id="AAPL", side="buy", quantity=Decimal("100"), price=Decimal("150"), commission=Decimal("10"), slippage=Decimal("5")),
            BacktestTrade(date=date(2025, 2, 1), instrument_id="AAPL", side="sell", quantity=Decimal("100"), price=Decimal("160"), commission=Decimal("10"), slippage=Decimal("5")),
        ]
        wr = _compute_win_rate(trades)
        assert wr == Decimal("1")  # one winning trade

    def test_compute_win_rate_empty(self) -> None:
        assert _compute_win_rate([]) == ZERO

    def test_compute_profit_factor(self) -> None:
        trades = [
            BacktestTrade(date=date(2025, 1, 1), instrument_id="AAPL", side="buy", quantity=Decimal("100"), price=Decimal("150"), commission=ZERO, slippage=ZERO),
            BacktestTrade(date=date(2025, 2, 1), instrument_id="AAPL", side="sell", quantity=Decimal("100"), price=Decimal("160"), commission=ZERO, slippage=ZERO),
        ]
        pf = _compute_profit_factor(trades)
        assert pf == ZERO  # no losses → ZERO (by convention)

    def test_compute_profit_factor_with_loss(self) -> None:
        trades = [
            BacktestTrade(date=date(2025, 1, 1), instrument_id="AAPL", side="buy", quantity=Decimal("100"), price=Decimal("160"), commission=ZERO, slippage=ZERO),
            BacktestTrade(date=date(2025, 2, 1), instrument_id="AAPL", side="sell", quantity=Decimal("100"), price=Decimal("150"), commission=ZERO, slippage=ZERO),
        ]
        pf = _compute_profit_factor(trades)
        assert pf == ZERO  # no wins either

    def test_compute_monthly_returns(self) -> None:
        curve = _make_curve([
            (date(2025, 1, 1), Decimal("1000")),
            (date(2025, 1, 31), Decimal("1100")),
            (date(2025, 2, 28), Decimal("1200")),
        ])
        monthly = _compute_monthly_returns(curve)
        assert len(monthly) == 2
        assert monthly[0].year == 2025
        assert monthly[0].month == 1

    def test_compute_monthly_returns_empty(self) -> None:
        assert _compute_monthly_returns([]) == []


class TestShouldRebalance:
    def test_first_day_always(self) -> None:
        assert _should_rebalance(date(2025, 1, 1), None, RebalanceFrequency.MONTHLY) is True

    def test_daily(self) -> None:
        assert _should_rebalance(date(2025, 1, 2), date(2025, 1, 1), RebalanceFrequency.DAILY) is True

    def test_weekly_same_week(self) -> None:
        # Monday and Tuesday of same week
        assert _should_rebalance(date(2025, 1, 7), date(2025, 1, 6), RebalanceFrequency.WEEKLY) is False

    def test_weekly_new_week(self) -> None:
        assert _should_rebalance(date(2025, 1, 13), date(2025, 1, 10), RebalanceFrequency.WEEKLY) is True

    def test_monthly_same_month(self) -> None:
        assert _should_rebalance(date(2025, 1, 15), date(2025, 1, 1), RebalanceFrequency.MONTHLY) is False

    def test_monthly_new_month(self) -> None:
        assert _should_rebalance(date(2025, 2, 1), date(2025, 1, 31), RebalanceFrequency.MONTHLY) is True

    def test_quarterly(self) -> None:
        assert _should_rebalance(date(2025, 4, 1), date(2025, 3, 31), RebalanceFrequency.QUARTERLY) is True
        assert _should_rebalance(date(2025, 2, 1), date(2025, 1, 31), RebalanceFrequency.QUARTERLY) is False


class TestBacktestEngine:
    def test_run_basic(self) -> None:
        engine = BacktestEngine()
        config = BacktestConfig(
            strategy_name="Test",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            initial_capital=Decimal("10000"),
            rebalance_frequency=RebalanceFrequency.DAILY,
            universe=["AAPL"],
        )
        price_data = _make_price_data(["AAPL"], days=31, start_price=150.0, daily_change=0.5)

        result = engine.run(config, price_data, equal_weight_signal)

        assert result.total_return >= ZERO
        assert len(result.equity_curve) > 0
        assert result.total_trades > 0

    def test_run_empty_dates(self) -> None:
        engine = BacktestEngine()
        config = BacktestConfig(
            strategy_name="Test",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            initial_capital=Decimal("10000"),
            rebalance_frequency=RebalanceFrequency.DAILY,
            universe=["AAPL"],
        )
        result = engine.run(config, {}, equal_weight_signal)
        assert result.total_return == ZERO
        assert result.equity_curve == []

    def test_run_two_instruments(self) -> None:
        engine = BacktestEngine()
        config = BacktestConfig(
            strategy_name="Test",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            initial_capital=Decimal("10000"),
            rebalance_frequency=RebalanceFrequency.DAILY,
            universe=["AAPL", "MSFT"],
        )
        price_data = _make_price_data(["AAPL", "MSFT"], days=31)

        result = engine.run(config, price_data, equal_weight_signal)

        assert result.total_trades > 0
        assert result.total_return != ZERO

    def test_monthly_rebalance(self) -> None:
        engine = BacktestEngine()
        config = BacktestConfig(
            strategy_name="Test",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
            initial_capital=Decimal("10000"),
            rebalance_frequency=RebalanceFrequency.MONTHLY,
            universe=["AAPL"],
        )
        price_data = _make_price_data(["AAPL"], days=90, start_price=150.0)

        result = engine.run(config, price_data, equal_weight_signal)

        # Monthly rebalance means fewer trades than daily
        assert result.total_trades >= 1
