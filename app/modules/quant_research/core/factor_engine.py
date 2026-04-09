"""Pure factor calculation functions — no I/O, no side effects."""

from __future__ import annotations

import math
import statistics
from datetime import date
from decimal import Decimal

ZERO = Decimal(0)
ONE = Decimal(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _z_scores(values: dict[str, Decimal]) -> dict[str, Decimal]:
    """Compute cross-sectional z-scores for a dict of raw values."""
    if len(values) < 2:
        return {k: ZERO for k in values}

    vals = list(values.values())
    mean = sum(vals) / len(vals)
    std = Decimal(str(statistics.stdev(float(v) for v in vals)))
    if std == ZERO:
        return {k: ZERO for k in values}
    return {k: (v - mean) / std for k, v in values.items()}


def _safe_return(current: Decimal, previous: Decimal) -> Decimal:
    """Compute a simple return, avoiding division by zero."""
    if previous == ZERO:
        return ZERO
    return (current - previous) / previous


# ---------------------------------------------------------------------------
# Factor computations
# ---------------------------------------------------------------------------


def compute_momentum_factor(
    prices: dict[str, list[tuple[date, Decimal]]],
    lookback: int = 252,
    skip_recent: int = 21,
) -> dict[str, Decimal]:
    """12-1 month momentum: return over lookback period, skipping most recent month."""
    raw: dict[str, Decimal] = {}
    for instrument, series in prices.items():
        if len(series) < lookback:
            continue
        sorted_series = sorted(series, key=lambda p: p[0])
        end_price = sorted_series[-(skip_recent + 1)][1]
        start_price = sorted_series[-lookback][1]
        raw[instrument] = _safe_return(end_price, start_price)
    return _z_scores(raw)


def compute_value_factor(
    fundamentals: dict[str, dict[str, Decimal]],
) -> dict[str, Decimal]:
    """Composite value: average z-score of E/P, B/P, S/P."""
    raw: dict[str, Decimal] = {}
    for instrument, data in fundamentals.items():
        price = data.get("price", ZERO)
        if price == ZERO:
            continue
        ep = data.get("earnings", ZERO) / price
        bp = data.get("book_value", ZERO) / price
        sp = data.get("sales", ZERO) / price if data.get("sales") else ZERO
        raw[instrument] = (ep + bp + sp) / Decimal(3)
    return _z_scores(raw)


def compute_size_factor(
    market_caps: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Log market cap, inverted (small = high exposure)."""
    raw: dict[str, Decimal] = {}
    for instrument, mcap in market_caps.items():
        if mcap > ZERO:
            raw[instrument] = -Decimal(str(math.log(float(mcap))))
    return _z_scores(raw)


def compute_quality_factor(
    fundamentals: dict[str, dict[str, Decimal]],
) -> dict[str, Decimal]:
    """ROE + debt/equity + earnings stability composite."""
    raw: dict[str, Decimal] = {}
    for instrument, data in fundamentals.items():
        equity = data.get("equity", ZERO)
        roe = data.get("earnings", ZERO) / equity if equity != ZERO else ZERO
        debt_equity = data.get("debt", ZERO) / equity if equity != ZERO else ZERO
        stability = data.get("earnings_stability", ZERO)
        # Higher ROE, lower debt/equity, higher stability = higher quality
        raw[instrument] = roe - debt_equity + stability
    return _z_scores(raw)


def compute_volatility_factor(
    prices: dict[str, list[tuple[date, Decimal]]],
    window: int = 63,
) -> dict[str, Decimal]:
    """Realized volatility over window, inverted (low vol = high exposure)."""
    raw: dict[str, Decimal] = {}
    for instrument, series in prices.items():
        if len(series) < window + 1:
            continue
        sorted_series = sorted(series, key=lambda p: p[0])
        recent = sorted_series[-window:]
        returns = [_safe_return(recent[i][1], recent[i - 1][1]) for i in range(1, len(recent))]
        if len(returns) < 2:
            continue
        vol = Decimal(str(statistics.stdev(float(r) for r in returns)))
        raw[instrument] = -vol  # inverted: low vol = high factor exposure
    return _z_scores(raw)


def compute_factor_returns(
    factor_exposures: dict[str, Decimal],
    instrument_returns: dict[str, Decimal],
) -> Decimal:
    """Long-short factor return: long top quintile, short bottom quintile."""
    if not factor_exposures:
        return ZERO

    sorted_instruments = sorted(factor_exposures.items(), key=lambda x: x[1])
    n = max(1, len(sorted_instruments) // 5)

    short_leg = sorted_instruments[:n]
    long_leg = sorted_instruments[-n:]

    long_return = sum(instrument_returns.get(inst, ZERO) for inst, _ in long_leg) / Decimal(n)
    short_return = sum(instrument_returns.get(inst, ZERO) for inst, _ in short_leg) / Decimal(n)
    return long_return - short_return


def compute_factor_correlation(
    factor_returns: dict[str, list[Decimal]],
) -> dict[str, dict[str, float]]:
    """Cross-factor correlation matrix."""
    factors = list(factor_returns.keys())
    matrix: dict[str, dict[str, float]] = {}

    for f1 in factors:
        matrix[f1] = {}
        for f2 in factors:
            if f1 == f2:
                matrix[f1][f2] = 1.0
                continue
            r1 = [float(v) for v in factor_returns[f1]]
            r2 = [float(v) for v in factor_returns[f2]]
            n = min(len(r1), len(r2))
            if n < 2:
                matrix[f1][f2] = 0.0
                continue
            r1, r2 = r1[:n], r2[:n]
            mean1, mean2 = statistics.mean(r1), statistics.mean(r2)
            cov = sum((a - mean1) * (b - mean2) for a, b in zip(r1, r2, strict=True)) / (n - 1)
            std1, std2 = statistics.stdev(r1), statistics.stdev(r2)
            if std1 == 0 or std2 == 0:
                matrix[f1][f2] = 0.0
            else:
                matrix[f1][f2] = round(cov / (std1 * std2), 6)
    return matrix


def decompose_portfolio(
    portfolio_weights: dict[str, Decimal],
    factor_exposures: dict[str, dict[str, Decimal]],
) -> tuple[dict[str, Decimal], Decimal]:
    """Decompose portfolio return into factor contributions + residual.

    Returns (factor_contributions, residual_pct).
    """
    factor_contributions: dict[str, Decimal] = {}
    total_explained = ZERO

    for factor_name, exposures in factor_exposures.items():
        contribution = sum(
            portfolio_weights.get(inst, ZERO) * exp for inst, exp in exposures.items()
        )
        factor_contributions[factor_name] = contribution
        total_explained += abs(contribution)

    total_weight = sum(abs(w) for w in portfolio_weights.values()) or ONE
    residual = ONE - min(total_explained / total_weight, ONE)
    return factor_contributions, residual
