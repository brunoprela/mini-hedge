"""Unit tests for tear sheet generation — pure quantitative computations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.backtesting.core.tear_sheet import (
    _compute_annual_returns,
    _compute_beta,
    _compute_cagr,
    _compute_cvar,
    _compute_daily_returns,
    _compute_trade_stats,
    _compute_underwater_curve,
    _compute_var,
    _compute_alpha,
    _compute_tracking_error,
    _compute_information_ratio,
    _extract_drawdown_periods,
    _rolling_sharpe_fn,
    _rolling_volatility_fn,
    generate_tear_sheet,
)
from datetime import datetime, timezone

from app.modules.backtesting.interfaces import (
    BacktestConfig,
    BacktestResult,
    BacktestTrade,
    EquityCurvePoint,
    RebalanceFrequency,
)

ZERO = Decimal(0)


def _make_equity_curve(
    values: list[tuple[date, Decimal]],
    benchmark_values: list[Decimal] | None = None,
) -> list[EquityCurvePoint]:
    points = []
    peak = ZERO
    for i, (d, v) in enumerate(values):
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak != ZERO else ZERO
        bv = benchmark_values[i] if benchmark_values else None
        points.append(EquityCurvePoint(date=d, portfolio_value=v, benchmark_value=bv, drawdown=dd))
    return points


class TestComputeCAGR:
    def test_positive_return(self) -> None:
        cagr = _compute_cagr(Decimal("1000"), Decimal("1100"), Decimal("1"))
        assert cagr > ZERO

    def test_zero_start_returns_zero(self) -> None:
        assert _compute_cagr(ZERO, Decimal("1000"), Decimal("1")) == ZERO

    def test_zero_years_returns_zero(self) -> None:
        assert _compute_cagr(Decimal("1000"), Decimal("1100"), ZERO) == ZERO

    def test_negative_total_return(self) -> None:
        # end_value=0 means total_return=0, log-based CAGR returns ZERO
        assert _compute_cagr(Decimal("1000"), ZERO, Decimal("1")) == ZERO


class TestComputeVaR:
    def test_basic_var(self) -> None:
        # Mix of gains and losses
        returns = [Decimal("-0.05"), Decimal("-0.02"), Decimal("0.01"), Decimal("0.03")]
        var = _compute_var(returns, 0.95)
        assert var >= ZERO  # VaR is reported as positive

    def test_empty_returns(self) -> None:
        assert _compute_var([], 0.95) == ZERO

    def test_all_positive_returns(self) -> None:
        returns = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")]
        var = _compute_var(returns, 0.95)
        assert var == ZERO  # no losses


class TestComputeCVaR:
    def test_basic_cvar(self) -> None:
        returns = [Decimal("-0.10"), Decimal("-0.05"), Decimal("-0.02"), Decimal("0.01"), Decimal("0.03")]
        cvar = _compute_cvar(returns, 0.95)
        assert cvar >= ZERO

    def test_empty_returns(self) -> None:
        assert _compute_cvar([], 0.95) == ZERO


class TestComputeBeta:
    def test_basic_beta(self) -> None:
        strategy = [Decimal("0.01"), Decimal("0.02"), Decimal("-0.01"), Decimal("0.03")]
        benchmark = [Decimal("0.005"), Decimal("0.01"), Decimal("-0.005"), Decimal("0.015")]
        beta = _compute_beta(strategy, benchmark)
        assert beta is not None
        assert beta > ZERO  # positively correlated

    def test_insufficient_data(self) -> None:
        assert _compute_beta([Decimal("0.01")], [Decimal("0.01")]) is None

    def test_zero_variance_benchmark(self) -> None:
        strategy = [Decimal("0.01"), Decimal("0.02")]
        benchmark = [Decimal("0.01"), Decimal("0.01")]  # no variance
        assert _compute_beta(strategy, benchmark) is None


class TestComputeAlpha:
    def test_basic_alpha(self) -> None:
        strategy = [Decimal("0.02"), Decimal("0.03"), Decimal("0.01"), Decimal("0.04")]
        benchmark = [Decimal("0.005"), Decimal("0.01"), Decimal("0.005"), Decimal("0.01")]
        alpha = _compute_alpha(strategy, benchmark)
        assert alpha is not None

    def test_insufficient_data(self) -> None:
        assert _compute_alpha([Decimal("0.01")], [Decimal("0.01")]) is None


class TestTrackingError:
    def test_basic(self) -> None:
        strategy = [Decimal("0.02"), Decimal("-0.01"), Decimal("0.03")]
        benchmark = [Decimal("0.01"), Decimal("-0.005"), Decimal("0.015")]
        te = _compute_tracking_error(strategy, benchmark)
        assert te is not None
        assert te > ZERO

    def test_insufficient_data(self) -> None:
        assert _compute_tracking_error([Decimal("0.01")], [Decimal("0.01")]) is None


class TestInformationRatio:
    def test_basic(self) -> None:
        strategy = [Decimal("0.03"), Decimal("0.02"), Decimal("0.04")]
        benchmark = [Decimal("0.01"), Decimal("0.01"), Decimal("0.01")]
        ir = _compute_information_ratio(strategy, benchmark)
        assert ir is not None

    def test_zero_tracking_error(self) -> None:
        # Identical returns → zero TE → None
        same = [Decimal("0.01"), Decimal("0.02")]
        assert _compute_information_ratio(same, same) is None


class TestRollingFunctions:
    def test_rolling_sharpe(self) -> None:
        returns = [Decimal("0.01")] * 5
        result = _rolling_sharpe_fn(returns)
        # Constant returns → high Sharpe or zero std edge case
        assert isinstance(result, Decimal)

    def test_rolling_sharpe_insufficient(self) -> None:
        assert _rolling_sharpe_fn([Decimal("0.01")]) == ZERO

    def test_rolling_volatility(self) -> None:
        returns = [Decimal("0.01"), Decimal("-0.01"), Decimal("0.02"), Decimal("-0.02")]
        vol = _rolling_volatility_fn(returns)
        assert vol > ZERO

    def test_rolling_volatility_insufficient(self) -> None:
        assert _rolling_volatility_fn([Decimal("0.01")]) == ZERO


class TestDailyReturns:
    def test_basic(self) -> None:
        curve = _make_equity_curve([
            (date(2025, 1, 1), Decimal("1000")),
            (date(2025, 1, 2), Decimal("1010")),
            (date(2025, 1, 3), Decimal("1005")),
        ])
        returns = _compute_daily_returns(curve)
        assert len(returns) == 2
        assert returns[0] == Decimal("10") / Decimal("1000")


class TestDrawdownPeriods:
    def test_single_drawdown_with_recovery(self) -> None:
        curve = _make_equity_curve([
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("90")),   # drawdown
            (date(2025, 1, 3), Decimal("85")),   # valley
            (date(2025, 1, 4), Decimal("95")),
            (date(2025, 1, 5), Decimal("100")),  # recovery
        ])
        periods = _extract_drawdown_periods(curve, top_n=5)
        assert len(periods) == 1
        assert periods[0].valley_date == date(2025, 1, 3)
        assert periods[0].recovery_date == date(2025, 1, 5)
        assert periods[0].max_drawdown == Decimal("15") / Decimal("100")

    def test_no_drawdown(self) -> None:
        curve = _make_equity_curve([
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("110")),
            (date(2025, 1, 3), Decimal("120")),
        ])
        assert _extract_drawdown_periods(curve) == []

    def test_open_drawdown_no_recovery(self) -> None:
        curve = _make_equity_curve([
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("90")),
            (date(2025, 1, 3), Decimal("85")),
        ])
        periods = _extract_drawdown_periods(curve)
        assert len(periods) == 1
        assert periods[0].recovery_date is None

    def test_empty_curve(self) -> None:
        assert _extract_drawdown_periods([]) == []


class TestUnderwaterCurve:
    def test_basic(self) -> None:
        curve = _make_equity_curve([
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("90")),
            (date(2025, 1, 3), Decimal("100")),
        ])
        underwater = _compute_underwater_curve(curve)
        assert len(underwater) == 3
        assert underwater[0].drawdown == ZERO
        assert underwater[1].drawdown < ZERO

    def test_empty(self) -> None:
        assert _compute_underwater_curve([]) == []


class TestAnnualReturns:
    def test_single_year(self) -> None:
        curve = _make_equity_curve([
            (date(2025, 1, 1), Decimal("1000")),
            (date(2025, 12, 31), Decimal("1100")),
        ])
        annual = _compute_annual_returns(curve)
        assert len(annual) == 1
        assert annual[0].year == 2025
        assert annual[0].return_pct == Decimal("0.1")

    def test_multiple_years(self) -> None:
        curve = _make_equity_curve([
            (date(2024, 1, 1), Decimal("1000")),
            (date(2024, 12, 31), Decimal("1100")),
            (date(2025, 6, 30), Decimal("1200")),
        ])
        annual = _compute_annual_returns(curve)
        assert len(annual) == 2

    def test_with_benchmark(self) -> None:
        curve = _make_equity_curve(
            [(date(2025, 1, 1), Decimal("1000")), (date(2025, 12, 31), Decimal("1100"))],
            benchmark_values=[Decimal("500"), Decimal("525")],
        )
        annual = _compute_annual_returns(curve)
        assert annual[0].benchmark_return_pct is not None

    def test_empty(self) -> None:
        assert _compute_annual_returns([]) == []


class TestTradeStats:
    def test_winning_and_losing_trades(self) -> None:
        trades = [
            BacktestTrade(date=date(2025, 1, 1), instrument_id="AAPL", side="buy", quantity=Decimal("100"), price=Decimal("150"), commission=Decimal("10"), slippage=Decimal("5")),
            BacktestTrade(date=date(2025, 2, 1), instrument_id="AAPL", side="sell", quantity=Decimal("100"), price=Decimal("160"), commission=Decimal("10"), slippage=Decimal("5")),
        ]
        stats = _compute_trade_stats(trades)
        # sell net: 160*100-10-5=15985, buy net: 150*100+10+5=15015, pnl=970
        assert stats["avg_win"] > ZERO
        assert stats["largest_win"] > ZERO
        assert stats["avg_loss"] == ZERO

    def test_losing_trade(self) -> None:
        trades = [
            BacktestTrade(date=date(2025, 1, 1), instrument_id="AAPL", side="buy", quantity=Decimal("100"), price=Decimal("160"), commission=Decimal("10"), slippage=Decimal("5")),
            BacktestTrade(date=date(2025, 2, 1), instrument_id="AAPL", side="sell", quantity=Decimal("100"), price=Decimal("150"), commission=Decimal("10"), slippage=Decimal("5")),
        ]
        stats = _compute_trade_stats(trades)
        assert stats["avg_loss"] < ZERO
        assert stats["largest_loss"] < ZERO

    def test_empty_trades(self) -> None:
        stats = _compute_trade_stats([])
        assert stats["avg_win"] == ZERO
        assert stats["avg_loss"] == ZERO


class TestGenerateTearSheet:
    def test_full_tear_sheet_generation(self) -> None:
        """Smoke test: generate a tear sheet from a minimal backtest result."""
        curve = _make_equity_curve([
            (date(2025, 1, d), Decimal(str(1000 + d * 2))) for d in range(1, 31)
        ])
        config = BacktestConfig(
            strategy_name="Test Strategy",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 30),
            initial_capital=Decimal("1000"),
            rebalance_frequency=RebalanceFrequency.DAILY,
            universe=["AAPL"],
        )
        result = BacktestResult(
            id="bt-1",
            config=config,
            status="completed",
            created_at=datetime.now(timezone.utc),
            total_return=Decimal("0.06"),
            annualized_return=Decimal("0.06"),
            sharpe_ratio=Decimal("2.5"),
            max_drawdown=Decimal("0"),
            volatility=Decimal("0.10"),
            calmar_ratio=Decimal("0.6"),
            sortino_ratio=Decimal("3.0"),
            win_rate=Decimal("0.6"),
            profit_factor=Decimal("1.5"),
            total_trades=10,
            avg_holding_period_days=Decimal("5"),
            equity_curve=curve,
            trades=[],
            monthly_returns=[],
        )

        sheet = generate_tear_sheet(result)

        assert sheet.strategy_name == "Test Strategy"
        assert sheet.total_return == Decimal("0.06")
        assert sheet.cagr >= ZERO
        assert sheet.var_95 >= ZERO
        assert sheet.cvar_95 >= ZERO
        assert sheet.beta is None  # no benchmark
        assert len(sheet.annual_returns) == 1
