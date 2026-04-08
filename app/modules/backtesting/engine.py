"""Core backtesting engine — pure computation, no database access."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.modules.backtesting.interface import (
    BacktestConfig,
    BacktestResult,
    BacktestStatus,
    BacktestTrade,
    EquityCurvePoint,
    MonthlyReturn,
    RebalanceFrequency,
)

if TYPE_CHECKING:
    from collections.abc import Callable

ZERO = Decimal(0)
ONE = Decimal(1)
BPS = Decimal("0.0001")
TRADING_DAYS_PER_YEAR = Decimal(252)


# ---------------------------------------------------------------------------
# Built-in signal functions
# ---------------------------------------------------------------------------


def equal_weight_signal(
    current_date: date,
    prices: dict[str, Decimal],
    positions: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Equal-weight all instruments in the universe."""
    n = len(prices)
    if n == 0:
        return {}
    weight = ONE / Decimal(n)
    return {inst: weight for inst in prices}


def momentum_signal(
    current_date: date,
    prices: dict[str, Decimal],
    positions: dict[str, Decimal],
    *,
    lookback: int = 20,
    _price_history: dict[str, list[tuple[date, Decimal]]] | None = None,
) -> dict[str, Decimal]:
    """Long top 50% of instruments by momentum (price change over lookback).

    Requires ``_price_history`` to be injected by the engine wrapper.
    Falls back to equal-weight if insufficient history.
    """
    if _price_history is None:
        return equal_weight_signal(current_date, prices, positions)

    returns: dict[str, Decimal] = {}
    for inst, hist in _price_history.items():
        relevant = [(d, p) for d, p in hist if d <= current_date]
        if len(relevant) < lookback + 1:
            continue
        old_price = relevant[-(lookback + 1)][1]
        if old_price != ZERO:
            returns[inst] = (relevant[-1][1] - old_price) / old_price

    if not returns:
        return equal_weight_signal(current_date, prices, positions)

    sorted_insts = sorted(returns, key=lambda i: returns[i], reverse=True)
    top_half = sorted_insts[: max(1, len(sorted_insts) // 2)]
    weight = ONE / Decimal(len(top_half))
    return {inst: weight for inst in top_half}


def mean_reversion_signal(
    current_date: date,
    prices: dict[str, Decimal],
    positions: dict[str, Decimal],
    *,
    lookback: int = 20,
    _price_history: dict[str, list[tuple[date, Decimal]]] | None = None,
) -> dict[str, Decimal]:
    """Long bottom 50% of instruments by return (mean-reversion).

    Requires ``_price_history`` to be injected by the engine wrapper.
    Falls back to equal-weight if insufficient history.
    """
    if _price_history is None:
        return equal_weight_signal(current_date, prices, positions)

    returns: dict[str, Decimal] = {}
    for inst, hist in _price_history.items():
        relevant = [(d, p) for d, p in hist if d <= current_date]
        if len(relevant) < lookback + 1:
            continue
        old_price = relevant[-(lookback + 1)][1]
        if old_price != ZERO:
            returns[inst] = (relevant[-1][1] - old_price) / old_price

    if not returns:
        return equal_weight_signal(current_date, prices, positions)

    sorted_insts = sorted(returns, key=lambda i: returns[i])
    bottom_half = sorted_insts[: max(1, len(sorted_insts) // 2)]
    weight = ONE / Decimal(len(bottom_half))
    return {inst: weight for inst in bottom_half}


BUILT_IN_SIGNALS: dict[
    str,
    Callable[[date, dict[str, Decimal], dict[str, Decimal]], dict[str, Decimal]],
] = {
    "equal_weight": equal_weight_signal,
    "momentum": momentum_signal,
    "mean_reversion": mean_reversion_signal,
}


# ---------------------------------------------------------------------------
# Metric computations (pure functions)
# ---------------------------------------------------------------------------


def _compute_returns(equity_curve: list[EquityCurvePoint]) -> list[Decimal]:
    """Compute daily returns from the equity curve."""
    returns: list[Decimal] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1].portfolio_value
        curr = equity_curve[i].portfolio_value
        if prev != ZERO:
            returns.append((curr - prev) / prev)
        else:
            returns.append(ZERO)
    return returns


def _compute_sharpe(
    returns: list[Decimal],
    risk_free_rate: float = 0.04,
) -> Decimal:
    """Compute annualized Sharpe ratio."""
    if len(returns) < 2:
        return ZERO
    daily_rf = Decimal(str(risk_free_rate)) / TRADING_DAYS_PER_YEAR
    excess = [r - daily_rf for r in returns]
    mean_excess = sum(excess) / Decimal(len(excess))
    variance = sum((r - mean_excess) ** 2 for r in excess) / Decimal(len(excess) - 1)
    std = Decimal(str(math.sqrt(float(variance))))
    if std == ZERO:
        return ZERO
    return (mean_excess / std) * Decimal(str(math.sqrt(float(TRADING_DAYS_PER_YEAR))))


def _compute_sortino(
    returns: list[Decimal],
    risk_free_rate: float = 0.04,
) -> Decimal:
    """Compute annualized Sortino ratio."""
    if len(returns) < 2:
        return ZERO
    daily_rf = Decimal(str(risk_free_rate)) / TRADING_DAYS_PER_YEAR
    excess = [r - daily_rf for r in returns]
    mean_excess = sum(excess) / Decimal(len(excess))
    downside = [r for r in excess if r < ZERO]
    if not downside:
        return ZERO
    downside_var = sum(r**2 for r in downside) / Decimal(len(downside))
    downside_std = Decimal(str(math.sqrt(float(downside_var))))
    if downside_std == ZERO:
        return ZERO
    return (mean_excess / downside_std) * Decimal(str(math.sqrt(float(TRADING_DAYS_PER_YEAR))))


def _compute_max_drawdown(equity_curve: list[EquityCurvePoint]) -> Decimal:
    """Compute maximum drawdown from equity curve."""
    if not equity_curve:
        return ZERO
    peak = equity_curve[0].portfolio_value
    max_dd = ZERO
    for pt in equity_curve:
        if pt.portfolio_value > peak:
            peak = pt.portfolio_value
        if peak != ZERO:
            dd = (peak - pt.portfolio_value) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _compute_calmar(annualized_return: Decimal, max_drawdown: Decimal) -> Decimal:
    """Compute Calmar ratio (annualized return / max drawdown)."""
    if max_drawdown == ZERO:
        return ZERO
    return annualized_return / max_drawdown


def _compute_volatility(returns: list[Decimal]) -> Decimal:
    """Compute annualized volatility."""
    if len(returns) < 2:
        return ZERO
    mean_r = sum(returns) / Decimal(len(returns))
    variance = sum((r - mean_r) ** 2 for r in returns) / Decimal(len(returns) - 1)
    daily_vol = Decimal(str(math.sqrt(float(variance))))
    return daily_vol * Decimal(str(math.sqrt(float(TRADING_DAYS_PER_YEAR))))


def _compute_win_rate(trades: list[BacktestTrade]) -> Decimal:
    """Compute win rate from trades (paired buy/sell by instrument)."""
    if not trades:
        return ZERO
    # Group trades by instrument, pair buys with subsequent sells
    by_instrument: dict[str, list[BacktestTrade]] = defaultdict(list)
    for t in trades:
        by_instrument[t.instrument_id].append(t)

    wins = 0
    total = 0
    for inst_trades in by_instrument.values():
        buys = [t for t in inst_trades if t.side == "buy"]
        sells = [t for t in inst_trades if t.side == "sell"]
        pairs = min(len(buys), len(sells))
        for i in range(pairs):
            total += 1
            sell_net = sells[i].price * sells[i].quantity - sells[i].commission - sells[i].slippage
            buy_net = buys[i].price * buys[i].quantity + buys[i].commission + buys[i].slippage
            if sell_net > buy_net:
                wins += 1

    if total == 0:
        return ZERO
    return Decimal(wins) / Decimal(total)


def _compute_profit_factor(trades: list[BacktestTrade]) -> Decimal:
    """Compute profit factor (gross profits / gross losses)."""
    if not trades:
        return ZERO
    by_instrument: dict[str, list[BacktestTrade]] = defaultdict(list)
    for t in trades:
        by_instrument[t.instrument_id].append(t)

    gross_profit = ZERO
    gross_loss = ZERO
    for inst_trades in by_instrument.values():
        buys = [t for t in inst_trades if t.side == "buy"]
        sells = [t for t in inst_trades if t.side == "sell"]
        pairs = min(len(buys), len(sells))
        for i in range(pairs):
            sell_net = sells[i].price * sells[i].quantity - sells[i].commission - sells[i].slippage
            buy_net = buys[i].price * buys[i].quantity + buys[i].commission + buys[i].slippage
            pnl = sell_net - buy_net
            if pnl > ZERO:
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)

    if gross_loss == ZERO:
        return ZERO
    return gross_profit / gross_loss


def _compute_monthly_returns(
    equity_curve: list[EquityCurvePoint],
) -> list[MonthlyReturn]:
    """Aggregate equity curve into monthly returns."""
    if not equity_curve:
        return []

    monthly: dict[tuple[int, int], list[EquityCurvePoint]] = defaultdict(list)
    for pt in equity_curve:
        monthly[(pt.date.year, pt.date.month)].append(pt)

    result: list[MonthlyReturn] = []
    for (year, month), points in sorted(monthly.items()):
        first_val = points[0].portfolio_value
        last_val = points[-1].portfolio_value
        ret = (last_val - first_val) / first_val if first_val != ZERO else ZERO

        bench_ret: Decimal | None = None
        if points[0].benchmark_value is not None and points[-1].benchmark_value is not None:
            bfirst = points[0].benchmark_value
            blast = points[-1].benchmark_value
            bench_ret = (blast - bfirst) / bfirst if bfirst != ZERO else ZERO

        result.append(
            MonthlyReturn(
                year=year,
                month=month,
                return_pct=ret,
                benchmark_return_pct=bench_ret,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Rebalance schedule helpers
# ---------------------------------------------------------------------------


def _should_rebalance(
    current: date,
    prev: date | None,
    frequency: RebalanceFrequency,
) -> bool:
    """Determine whether to rebalance on this date."""
    if prev is None:
        return True  # always rebalance on first day
    if frequency == RebalanceFrequency.DAILY:
        return True
    if frequency == RebalanceFrequency.WEEKLY:
        return current.isocalendar()[1] != prev.isocalendar()[1]
    if frequency == RebalanceFrequency.MONTHLY:
        return current.month != prev.month
    if frequency == RebalanceFrequency.QUARTERLY:
        return (current.month - 1) // 3 != (prev.month - 1) // 3
    return False


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """Event-driven backtesting engine."""

    def run(
        self,
        config: BacktestConfig,
        price_data: dict[str, list[tuple[date, Decimal]]],
        signal_fn: Callable[
            [date, dict[str, Decimal], dict[str, Decimal]],
            dict[str, Decimal],
        ],
    ) -> BacktestResult:
        """Run backtest with the given signal function.

        ``signal_fn`` receives ``(date, current_prices, current_positions)``
        and returns target weights (instrument_id -> fraction of portfolio).

        The engine handles:
        - Portfolio rebalancing based on target weights
        - Slippage and commission modelling
        - Equity curve tracking
        - Drawdown calculation
        - Performance metric computation
        """
        # Build a sorted set of all trading dates across instruments
        all_dates: set[date] = set()
        for points in price_data.values():
            for d, _ in points:
                if config.start_date <= d <= config.end_date:
                    all_dates.add(d)
        trading_dates = sorted(all_dates)

        if not trading_dates:
            return self._empty_result(config)

        # Build price lookup: instrument -> date -> price
        price_lookup: dict[str, dict[date, Decimal]] = defaultdict(dict)
        for inst, points in price_data.items():
            for d, p in points:
                price_lookup[inst][d] = p

        slippage_rate = Decimal(config.slippage_bps) * BPS
        commission_rate = Decimal(config.commission_bps) * BPS

        # State
        cash = config.initial_capital
        holdings: dict[str, Decimal] = {}  # instrument_id -> quantity
        equity_curve: list[EquityCurvePoint] = []
        trades: list[BacktestTrade] = []
        peak = config.initial_capital
        prev_date: date | None = None

        for current_date in trading_dates:
            # Current prices for instruments available today
            current_prices: dict[str, Decimal] = {}
            for inst in config.universe:
                if current_date in price_lookup.get(inst, {}):
                    current_prices[inst] = price_lookup[inst][current_date]

            if not current_prices:
                continue

            # Compute current portfolio value
            portfolio_value = cash
            current_positions: dict[str, Decimal] = {}
            for inst, qty in holdings.items():
                if inst in current_prices:
                    mv = qty * current_prices[inst]
                    portfolio_value += mv
                    current_positions[inst] = mv

            # Rebalance?
            if _should_rebalance(current_date, prev_date, config.rebalance_frequency):
                target_weights = signal_fn(current_date, current_prices, current_positions)

                # Execute rebalancing trades
                for inst in set(list(holdings.keys()) + list(target_weights.keys())):
                    if inst not in current_prices:
                        continue
                    price = current_prices[inst]
                    if price == ZERO:
                        continue

                    target_value = portfolio_value * target_weights.get(inst, ZERO)
                    current_value = holdings.get(inst, ZERO) * price
                    diff_value = target_value - current_value

                    if abs(diff_value) < ONE:
                        continue

                    trade_qty = abs(diff_value) / price
                    trade_value = trade_qty * price
                    commission = trade_value * commission_rate
                    slippage = trade_value * slippage_rate

                    if diff_value > ZERO:
                        # Buy
                        total_cost = trade_value + commission + slippage
                        if total_cost > cash:
                            # Scale down to available cash
                            scale = cash / total_cost if total_cost > ZERO else ZERO
                            trade_qty *= scale
                            trade_value = trade_qty * price
                            commission = trade_value * commission_rate
                            slippage = trade_value * slippage_rate
                            total_cost = trade_value + commission + slippage

                        cash -= total_cost
                        holdings[inst] = holdings.get(inst, ZERO) + trade_qty
                        trades.append(
                            BacktestTrade(
                                date=current_date,
                                instrument_id=inst,
                                side="buy",
                                quantity=trade_qty,
                                price=price,
                                commission=commission,
                                slippage=slippage,
                            )
                        )
                    else:
                        # Sell
                        sell_qty = min(trade_qty, holdings.get(inst, ZERO))
                        if sell_qty <= ZERO:
                            continue
                        sell_value = sell_qty * price
                        commission = sell_value * commission_rate
                        slippage = sell_value * slippage_rate
                        proceeds = sell_value - commission - slippage
                        cash += proceeds
                        holdings[inst] = holdings.get(inst, ZERO) - sell_qty
                        if holdings[inst] <= ZERO:
                            del holdings[inst]
                        trades.append(
                            BacktestTrade(
                                date=current_date,
                                instrument_id=inst,
                                side="sell",
                                quantity=sell_qty,
                                price=price,
                                commission=commission,
                                slippage=slippage,
                            )
                        )

            # Recalculate portfolio value after trades
            portfolio_value = cash
            for inst, qty in holdings.items():
                if inst in current_prices:
                    portfolio_value += qty * current_prices[inst]

            if portfolio_value > peak:
                peak = portfolio_value
            drawdown = (peak - portfolio_value) / peak if peak != ZERO else ZERO

            equity_curve.append(
                EquityCurvePoint(
                    date=current_date,
                    portfolio_value=portfolio_value,
                    benchmark_value=None,
                    drawdown=drawdown,
                )
            )
            prev_date = current_date

        # Compute metrics
        returns = _compute_returns(equity_curve)
        final_value = equity_curve[-1].portfolio_value if equity_curve else config.initial_capital
        total_return = (
            (final_value - config.initial_capital) / config.initial_capital
            if config.initial_capital != ZERO
            else ZERO
        )
        n_days = len(trading_dates)
        years = Decimal(n_days) / TRADING_DAYS_PER_YEAR
        annualized_return = (
            Decimal(str((float(ONE + total_return)) ** (1 / float(years)) - 1))
            if years > ZERO
            else ZERO
        )
        max_dd = _compute_max_drawdown(equity_curve)
        sharpe = _compute_sharpe(returns)
        sortino = _compute_sortino(returns)
        volatility = _compute_volatility(returns)
        calmar = _compute_calmar(annualized_return, max_dd)
        win_rate = _compute_win_rate(trades)
        profit_factor = _compute_profit_factor(trades)
        monthly = _compute_monthly_returns(equity_curve)

        # Avg holding period (rough: total days / number of round-trip trades)
        total_trades = len(trades)
        round_trips = total_trades // 2
        avg_holding = Decimal(n_days) / Decimal(round_trips) if round_trips > 0 else Decimal(n_days)

        return BacktestResult(
            id="",  # assigned by caller
            config=config,
            status=BacktestStatus.COMPLETED,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            volatility=volatility,
            calmar_ratio=calmar,
            sortino_ratio=sortino,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            avg_holding_period_days=avg_holding,
            equity_curve=equity_curve,
            trades=trades,
            monthly_returns=monthly,
            created_at=datetime.min,  # assigned by caller
            completed_at=None,
        )

    @staticmethod
    def _empty_result(config: BacktestConfig) -> BacktestResult:
        """Return an empty result when no trading dates exist."""
        return BacktestResult(
            id="",
            config=config,
            status=BacktestStatus.COMPLETED,
            total_return=ZERO,
            annualized_return=ZERO,
            sharpe_ratio=ZERO,
            max_drawdown=ZERO,
            volatility=ZERO,
            calmar_ratio=ZERO,
            sortino_ratio=ZERO,
            win_rate=ZERO,
            profit_factor=ZERO,
            total_trades=0,
            avg_holding_period_days=ZERO,
            equity_curve=[],
            trades=[],
            monthly_returns=[],
            created_at=datetime.min,
            completed_at=None,
        )
