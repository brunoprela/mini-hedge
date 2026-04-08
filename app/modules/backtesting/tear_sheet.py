"""Quantitative tear sheet generation for backtests.

Produces the same analytics as pyfolio/quantstats tear sheets:
strategy summary, rolling metrics, drawdown analysis, monthly heatmap,
and risk-adjusted return decomposition.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.modules.backtesting.interface import (
        BacktestResult,
        BacktestTrade,
        EquityCurvePoint,
    )

ZERO = Decimal(0)
ONE = Decimal(1)
TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class RollingMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    value: Decimal


class DrawdownPeriod(BaseModel):
    model_config = ConfigDict(frozen=True)

    peak_date: date
    valley_date: date
    recovery_date: date | None
    max_drawdown: Decimal
    duration_days: int
    recovery_days: int | None


class UnderwaterPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    drawdown: Decimal  # negative


class AnnualReturn(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: int
    return_pct: Decimal
    benchmark_return_pct: Decimal | None


class TearSheet(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Strategy Summary
    strategy_name: str
    period: str  # "2020-01-01 to 2024-12-31"
    total_return: Decimal
    cagr: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    max_drawdown: Decimal
    volatility: Decimal

    # Risk Metrics
    var_95: Decimal
    cvar_95: Decimal
    beta: Decimal | None
    alpha: Decimal | None
    information_ratio: Decimal | None
    tracking_error: Decimal | None

    # Trade Analysis
    total_trades: int
    win_rate: Decimal
    profit_factor: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    avg_holding_period_days: Decimal

    # Rolling Metrics
    rolling_sharpe: list[RollingMetric]
    rolling_volatility: list[RollingMetric]
    rolling_beta: list[RollingMetric]

    # Drawdown Analysis
    drawdowns: list[DrawdownPeriod]
    underwater_curve: list[UnderwaterPoint]

    # Monthly/Annual Returns
    monthly_returns: list  # MonthlyReturn from interface
    annual_returns: list[AnnualReturn]


# ---------------------------------------------------------------------------
# Pure computation functions
# ---------------------------------------------------------------------------


def _compute_cagr(start_value: Decimal, end_value: Decimal, years: Decimal) -> Decimal:
    """Compound annual growth rate."""
    if start_value <= ZERO or years <= ZERO:
        return ZERO
    total_return = float(end_value / start_value)
    if total_return <= 0:
        return ZERO
    cagr = total_return ** (1.0 / float(years)) - 1.0
    return Decimal(str(round(cagr, 8)))


def _compute_var(returns: list[Decimal], confidence: float = 0.95) -> Decimal:
    """Historical Value at Risk — percentile of losses.

    Returns a positive number representing the potential loss at the given
    confidence level (e.g. 0.95 means 5th-percentile return).
    """
    if not returns:
        return ZERO
    sorted_returns = sorted(returns)
    index = int(len(sorted_returns) * (1 - confidence))
    index = max(0, min(index, len(sorted_returns) - 1))
    var = sorted_returns[index]
    # VaR is reported as a positive loss amount
    return -var if var < ZERO else ZERO


def _compute_cvar(returns: list[Decimal], confidence: float = 0.95) -> Decimal:
    """Conditional VaR (Expected Shortfall) — mean of returns below VaR threshold."""
    if not returns:
        return ZERO
    sorted_returns = sorted(returns)
    cutoff = int(len(sorted_returns) * (1 - confidence))
    cutoff = max(1, cutoff)
    tail = sorted_returns[:cutoff]
    if not tail:
        return ZERO
    mean_tail = sum(tail) / Decimal(len(tail))
    return -mean_tail if mean_tail < ZERO else ZERO


def _compute_beta(
    strategy_returns: list[Decimal],
    benchmark_returns: list[Decimal],
) -> Decimal | None:
    """Beta = Cov(strategy, benchmark) / Var(benchmark)."""
    n = min(len(strategy_returns), len(benchmark_returns))
    if n < 2:
        return None
    s = [float(strategy_returns[i]) for i in range(n)]
    b = [float(benchmark_returns[i]) for i in range(n)]
    s_mean = sum(s) / n
    b_mean = sum(b) / n
    cov = sum((s[i] - s_mean) * (b[i] - b_mean) for i in range(n)) / (n - 1)
    b_var = sum((b[i] - b_mean) ** 2 for i in range(n)) / (n - 1)
    if b_var == 0:
        return None
    return Decimal(str(round(cov / b_var, 8)))


def _compute_alpha(
    strategy_returns: list[Decimal],
    benchmark_returns: list[Decimal],
    risk_free_rate: float = 0.04,
) -> Decimal | None:
    """Jensen's alpha (annualized).

    alpha = annualized(mean_strategy - rf) - beta * annualized(mean_benchmark - rf)
    """
    n = min(len(strategy_returns), len(benchmark_returns))
    if n < 2:
        return None
    beta = _compute_beta(strategy_returns, benchmark_returns)
    if beta is None:
        return None
    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    s_excess = sum(float(strategy_returns[i]) - daily_rf for i in range(n)) / n
    b_excess = sum(float(benchmark_returns[i]) - daily_rf for i in range(n)) / n
    daily_alpha = s_excess - float(beta) * b_excess
    annualized = daily_alpha * TRADING_DAYS_PER_YEAR
    return Decimal(str(round(annualized, 8)))


def _compute_tracking_error(
    strategy_returns: list[Decimal],
    benchmark_returns: list[Decimal],
) -> Decimal | None:
    """Tracking error = annualized std of excess returns."""
    n = min(len(strategy_returns), len(benchmark_returns))
    if n < 2:
        return None
    excess = [float(strategy_returns[i]) - float(benchmark_returns[i]) for i in range(n)]
    mean_ex = sum(excess) / n
    variance = sum((e - mean_ex) ** 2 for e in excess) / (n - 1)
    daily_te = math.sqrt(variance)
    annualized = daily_te * math.sqrt(TRADING_DAYS_PER_YEAR)
    return Decimal(str(round(annualized, 8)))


def _compute_information_ratio(
    strategy_returns: list[Decimal],
    benchmark_returns: list[Decimal],
) -> Decimal | None:
    """Information ratio = annualized excess return / tracking error."""
    n = min(len(strategy_returns), len(benchmark_returns))
    if n < 2:
        return None
    te = _compute_tracking_error(strategy_returns, benchmark_returns)
    if te is None or te == ZERO:
        return None
    excess = [float(strategy_returns[i]) - float(benchmark_returns[i]) for i in range(n)]
    mean_excess = sum(excess) / n
    annualized_excess = mean_excess * TRADING_DAYS_PER_YEAR
    return Decimal(str(round(annualized_excess / float(te), 8)))


def _compute_rolling_metric(
    dates: list[date],
    values: list[Decimal],
    window: int,
    metric_fn: object,  # Callable[[list[Decimal]], Decimal]
) -> list[RollingMetric]:
    """Apply metric_fn over a rolling window of values."""
    results: list[RollingMetric] = []
    for i in range(window, len(values) + 1):
        window_vals = values[i - window : i]
        val = metric_fn(window_vals)  # type: ignore[operator]
        results.append(RollingMetric(date=dates[i - 1], value=val))
    return results


def _rolling_sharpe_fn(returns: list[Decimal], risk_free_rate: float = 0.04) -> Decimal:
    """Sharpe ratio for a window of returns (annualized)."""
    if len(returns) < 2:
        return ZERO
    daily_rf = Decimal(str(risk_free_rate)) / Decimal(TRADING_DAYS_PER_YEAR)
    excess = [r - daily_rf for r in returns]
    mean_ex = sum(excess) / Decimal(len(excess))
    variance = sum((r - mean_ex) ** 2 for r in excess) / Decimal(len(excess) - 1)
    std = Decimal(str(math.sqrt(float(variance))))
    if std == ZERO:
        return ZERO
    return (mean_ex / std) * Decimal(str(math.sqrt(TRADING_DAYS_PER_YEAR)))


def _rolling_volatility_fn(returns: list[Decimal]) -> Decimal:
    """Annualized volatility for a window of returns."""
    if len(returns) < 2:
        return ZERO
    mean_r = sum(returns) / Decimal(len(returns))
    variance = sum((r - mean_r) ** 2 for r in returns) / Decimal(len(returns) - 1)
    daily_vol = Decimal(str(math.sqrt(float(variance))))
    return daily_vol * Decimal(str(math.sqrt(TRADING_DAYS_PER_YEAR)))


def _extract_drawdown_periods(
    equity_curve: list[EquityCurvePoint],
    top_n: int = 5,
) -> list[DrawdownPeriod]:
    """Identify top N drawdown periods with peak, valley, and recovery dates."""
    if not equity_curve:
        return []

    # Track peak and drawdown state
    peak = equity_curve[0].portfolio_value
    peak_date = equity_curve[0].date
    in_drawdown = False
    current_valley = equity_curve[0].portfolio_value
    current_valley_date = equity_curve[0].date
    current_peak_date = equity_curve[0].date
    current_max_dd = ZERO

    periods: list[dict] = []

    for pt in equity_curve:
        if pt.portfolio_value >= peak:
            # New high — close out any active drawdown
            if in_drawdown:
                periods.append(
                    {
                        "peak_date": current_peak_date,
                        "valley_date": current_valley_date,
                        "recovery_date": pt.date,
                        "max_drawdown": current_max_dd,
                    }
                )
                in_drawdown = False
            peak = pt.portfolio_value
            peak_date = pt.date
        else:
            # In a drawdown
            dd = (peak - pt.portfolio_value) / peak if peak != ZERO else ZERO
            if not in_drawdown:
                in_drawdown = True
                current_peak_date = peak_date
                current_valley = pt.portfolio_value
                current_valley_date = pt.date
                current_max_dd = dd
            elif pt.portfolio_value < current_valley:
                current_valley = pt.portfolio_value
                current_valley_date = pt.date
                current_max_dd = dd

    # Close any open drawdown (no recovery yet)
    if in_drawdown:
        periods.append(
            {
                "peak_date": current_peak_date,
                "valley_date": current_valley_date,
                "recovery_date": None,
                "max_drawdown": current_max_dd,
            }
        )

    # Sort by severity, take top N
    periods.sort(key=lambda p: p["max_drawdown"], reverse=True)
    top = periods[:top_n]

    result: list[DrawdownPeriod] = []
    for p in top:
        peak_d: date = p["peak_date"]
        valley_d: date = p["valley_date"]
        recovery_d: date | None = p["recovery_date"]
        duration = (valley_d - peak_d).days
        recovery_days = (recovery_d - valley_d).days if recovery_d else None
        result.append(
            DrawdownPeriod(
                peak_date=peak_d,
                valley_date=valley_d,
                recovery_date=recovery_d,
                max_drawdown=p["max_drawdown"],
                duration_days=duration,
                recovery_days=recovery_days,
            )
        )
    return result


def _compute_underwater_curve(
    equity_curve: list[EquityCurvePoint],
) -> list[UnderwaterPoint]:
    """Full drawdown timeseries (always <= 0)."""
    if not equity_curve:
        return []
    peak = equity_curve[0].portfolio_value
    result: list[UnderwaterPoint] = []
    for pt in equity_curve:
        if pt.portfolio_value > peak:
            peak = pt.portfolio_value
        dd = (pt.portfolio_value - peak) / peak if peak != ZERO else ZERO
        result.append(UnderwaterPoint(date=pt.date, drawdown=dd))
    return result


def _compute_annual_returns(
    equity_curve: list[EquityCurvePoint],
) -> list[AnnualReturn]:
    """Aggregate equity curve into annual returns."""
    if not equity_curve:
        return []
    by_year: dict[int, list[EquityCurvePoint]] = defaultdict(list)
    for pt in equity_curve:
        by_year[pt.date.year].append(pt)

    result: list[AnnualReturn] = []
    for year in sorted(by_year):
        points = by_year[year]
        first_val = points[0].portfolio_value
        last_val = points[-1].portfolio_value
        ret = (last_val - first_val) / first_val if first_val != ZERO else ZERO

        bench_ret: Decimal | None = None
        if points[0].benchmark_value is not None and points[-1].benchmark_value is not None:
            bfirst = points[0].benchmark_value
            blast = points[-1].benchmark_value
            bench_ret = (blast - bfirst) / bfirst if bfirst != ZERO else ZERO

        result.append(AnnualReturn(year=year, return_pct=ret, benchmark_return_pct=bench_ret))
    return result


def _compute_trade_stats(
    trades: list[BacktestTrade],
) -> dict:
    """Compute avg win, avg loss, largest win, largest loss from paired trades."""
    if not trades:
        return {
            "avg_win": ZERO,
            "avg_loss": ZERO,
            "largest_win": ZERO,
            "largest_loss": ZERO,
        }

    by_instrument: dict[str, list[BacktestTrade]] = defaultdict(list)
    for t in trades:
        by_instrument[t.instrument_id].append(t)

    wins: list[Decimal] = []
    losses: list[Decimal] = []

    for inst_trades in by_instrument.values():
        buys = [t for t in inst_trades if t.side == "buy"]
        sells = [t for t in inst_trades if t.side == "sell"]
        pairs = min(len(buys), len(sells))
        for i in range(pairs):
            sell_net = sells[i].price * sells[i].quantity - sells[i].commission - sells[i].slippage
            buy_net = buys[i].price * buys[i].quantity + buys[i].commission + buys[i].slippage
            pnl = sell_net - buy_net
            if pnl > ZERO:
                wins.append(pnl)
            elif pnl < ZERO:
                losses.append(pnl)

    avg_win = sum(wins) / Decimal(len(wins)) if wins else ZERO
    avg_loss = sum(losses) / Decimal(len(losses)) if losses else ZERO
    largest_win = max(wins) if wins else ZERO
    largest_loss = min(losses) if losses else ZERO  # most negative

    return {
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
    }


def _compute_daily_returns(equity_curve: list[EquityCurvePoint]) -> list[Decimal]:
    """Daily returns from equity curve."""
    returns: list[Decimal] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1].portfolio_value
        curr = equity_curve[i].portfolio_value
        if prev != ZERO:
            returns.append((curr - prev) / prev)
        else:
            returns.append(ZERO)
    return returns


def _compute_benchmark_returns(
    equity_curve: list[EquityCurvePoint],
) -> list[Decimal] | None:
    """Daily benchmark returns from equity curve, or None if no benchmark data."""
    if not equity_curve or equity_curve[0].benchmark_value is None:
        return None
    returns: list[Decimal] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1].benchmark_value
        curr = equity_curve[i].benchmark_value
        if prev is None or curr is None:
            return None
        if prev != ZERO:
            returns.append((curr - prev) / prev)
        else:
            returns.append(ZERO)
    return returns


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_tear_sheet(result: BacktestResult) -> TearSheet:
    """Generate a comprehensive quantitative tear sheet from backtest results."""
    ec = result.equity_curve
    daily_returns = _compute_daily_returns(ec)
    benchmark_returns = _compute_benchmark_returns(ec)
    dates = [pt.date for pt in ec[1:]]  # aligned with daily_returns

    # Period
    period = f"{ec[0].date.isoformat()} to {ec[-1].date.isoformat()}" if ec else "N/A"

    # CAGR
    n_days = len(ec)
    years = Decimal(n_days) / Decimal(TRADING_DAYS_PER_YEAR) if n_days > 0 else ZERO
    start_val = result.config.initial_capital
    end_val = ec[-1].portfolio_value if ec else start_val
    cagr = _compute_cagr(start_val, end_val, years)

    # VaR / CVaR
    var_95 = _compute_var(daily_returns)
    cvar_95 = _compute_cvar(daily_returns)

    # Benchmark-relative metrics
    beta = _compute_beta(daily_returns, benchmark_returns) if benchmark_returns else None
    alpha = _compute_alpha(daily_returns, benchmark_returns) if benchmark_returns else None
    ir = _compute_information_ratio(daily_returns, benchmark_returns) if benchmark_returns else None
    te = _compute_tracking_error(daily_returns, benchmark_returns) if benchmark_returns else None

    # Trade stats
    trade_stats = _compute_trade_stats(result.trades)

    # Rolling metrics (63-day Sharpe, 21-day vol)
    rolling_sharpe = _compute_rolling_metric(dates, daily_returns, 63, _rolling_sharpe_fn)
    rolling_vol = _compute_rolling_metric(dates, daily_returns, 21, _rolling_volatility_fn)

    # Rolling beta (63-day)
    rolling_beta_list: list[RollingMetric] = []
    if benchmark_returns:
        for i in range(63, len(daily_returns) + 1):
            s_window = daily_returns[i - 63 : i]
            b_window = benchmark_returns[i - 63 : i]
            b = _compute_beta(s_window, b_window)
            if b is not None:
                rolling_beta_list.append(RollingMetric(date=dates[i - 1], value=b))

    # Drawdown analysis
    drawdowns = _extract_drawdown_periods(ec, top_n=5)
    underwater = _compute_underwater_curve(ec)

    # Annual returns
    annual_returns = _compute_annual_returns(ec)

    return TearSheet(
        strategy_name=result.config.strategy_name,
        period=period,
        total_return=result.total_return,
        cagr=cagr,
        sharpe_ratio=result.sharpe_ratio,
        sortino_ratio=result.sortino_ratio,
        calmar_ratio=result.calmar_ratio,
        max_drawdown=result.max_drawdown,
        volatility=result.volatility,
        var_95=var_95,
        cvar_95=cvar_95,
        beta=beta,
        alpha=alpha,
        information_ratio=ir,
        tracking_error=te,
        total_trades=result.total_trades,
        win_rate=result.win_rate,
        profit_factor=result.profit_factor,
        avg_win=trade_stats["avg_win"],
        avg_loss=trade_stats["avg_loss"],
        largest_win=trade_stats["largest_win"],
        largest_loss=trade_stats["largest_loss"],
        avg_holding_period_days=result.avg_holding_period_days,
        rolling_sharpe=rolling_sharpe,
        rolling_volatility=rolling_vol,
        rolling_beta=rolling_beta_list,
        drawdowns=drawdowns,
        underwater_curve=underwater,
        monthly_returns=result.monthly_returns,
        annual_returns=annual_returns,
    )
