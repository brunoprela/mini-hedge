"""Stateless alpha engine calculators — pure functions, no I/O.

What-if scenario analysis and portfolio optimization.
Uses NumPy for optimization (avoiding PyPortfolioOpt dependency for now;
can be swapped in later for more sophisticated objectives).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import numpy as np

from app.modules.alpha_engine.interface import (
    HypotheticalTrade,
    OptimizationObjective,
    OptimizationResult,
    OptimizationWeight,
    OrderIntent,
    WhatIfPosition,
    WhatIfResult,
)

ZERO = Decimal(0)
_Q4 = Decimal("0.0001")
_Q6 = Decimal("0.000001")


def _to_dec4(v: float) -> Decimal:
    return Decimal(str(v)).quantize(_Q4)


def _to_dec6(v: float) -> Decimal:
    return Decimal(str(v)).quantize(_Q6)


# ---------------------------------------------------------------------------
# What-if analysis
# ---------------------------------------------------------------------------


def run_what_if(
    portfolio_id: UUID,
    scenario_name: str,
    current_positions: dict[str, tuple[Decimal, Decimal]],
    trades: list[HypotheticalTrade],
    prices: dict[str, Decimal],
    nav: float,
) -> WhatIfResult:
    """Evaluate hypothetical trades against current portfolio.

    Args:
        current_positions: instrument_id -> (quantity, market_value)
        trades: list of hypothetical trades
        prices: instrument_id -> current market price
        nav: current NAV
    """
    # Apply trades to build proposed positions
    proposed_qty: dict[str, Decimal] = {iid: qty for iid, (qty, _) in current_positions.items()}
    for trade in trades:
        current = proposed_qty.get(trade.instrument_id, ZERO)
        if trade.side == "buy":
            proposed_qty[trade.instrument_id] = current + trade.quantity
        else:
            proposed_qty[trade.instrument_id] = current - trade.quantity

    # Calculate proposed values
    proposed_nav = 0.0
    positions: list[WhatIfPosition] = []

    all_ids = set(current_positions.keys()) | set(proposed_qty.keys())
    for iid in sorted(all_ids):
        cur_qty, cur_val = current_positions.get(iid, (ZERO, ZERO))
        prop_qty = proposed_qty.get(iid, ZERO)
        price = prices.get(iid, ZERO)
        prop_val = prop_qty * price

        proposed_nav += float(prop_val)

        cur_weight = float(cur_val) / nav if nav > 0 else 0.0
        # Proposed weight calculated after all positions valued

        positions.append(
            WhatIfPosition(
                instrument_id=iid,
                current_quantity=cur_qty,
                proposed_quantity=prop_qty,
                current_value=cur_val,
                proposed_value=prop_val.quantize(_Q4),
                current_weight=_to_dec6(cur_weight),
                proposed_weight=ZERO,  # filled below
            )
        )

    # Fill proposed weights
    final_positions = []
    for pos in positions:
        prop_weight = float(pos.proposed_value) / proposed_nav if proposed_nav > 0 else 0.0
        final_positions.append(
            WhatIfPosition(
                instrument_id=pos.instrument_id,
                current_quantity=pos.current_quantity,
                proposed_quantity=pos.proposed_quantity,
                current_value=pos.current_value,
                proposed_value=pos.proposed_value,
                current_weight=pos.current_weight,
                proposed_weight=_to_dec6(prop_weight),
            )
        )

    nav_change = proposed_nav - nav
    nav_change_pct = nav_change / nav if nav > 0 else 0.0

    return WhatIfResult(
        portfolio_id=portfolio_id,
        scenario_name=scenario_name,
        current_nav=_to_dec4(nav),
        proposed_nav=_to_dec4(proposed_nav),
        nav_change=_to_dec4(nav_change),
        nav_change_pct=_to_dec6(nav_change_pct),
        positions=final_positions,
        calculated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Portfolio optimization
# ---------------------------------------------------------------------------


def optimize_portfolio(
    portfolio_id: UUID,
    objective: OptimizationObjective,
    current_weights: dict[str, float],
    returns_matrix: np.ndarray,  # type: ignore[type-arg]
    instrument_ids: list[str],
    prices: dict[str, float],
    nav: float,
) -> OptimizationResult:
    """Optimize portfolio weights using mean-variance framework.

    Supports min_variance, max_sharpe, and risk_parity objectives.
    Uses analytical solutions where possible, numerical otherwise.
    """
    n = len(instrument_ids)
    if n == 0:
        return _empty_result(portfolio_id, objective)

    # Expected returns and covariance
    mu = np.mean(returns_matrix, axis=0) * 252  # annualized
    cov = np.cov(returns_matrix.T) * 252  # annualized

    if cov.ndim == 0:
        cov = np.array([[float(cov)]])

    if objective == OptimizationObjective.MIN_VARIANCE:
        target_weights = _min_variance(cov, n)
    elif objective == OptimizationObjective.MAX_SHARPE:
        target_weights = _max_sharpe(mu, cov, n)
    else:  # risk_parity
        target_weights = _risk_parity(cov, n)

    # Calculate expected portfolio metrics
    exp_return = float(target_weights @ mu)
    exp_risk = float(np.sqrt(target_weights @ cov @ target_weights))
    sharpe = exp_return / exp_risk if exp_risk > 1e-10 else None

    # Build weight deltas and order intents
    weights: list[OptimizationWeight] = []
    intents: list[OrderIntent] = []

    for i, iid in enumerate(instrument_ids):
        cur_w = current_weights.get(iid, 0.0)
        tgt_w = float(target_weights[i])
        delta_w = tgt_w - cur_w
        delta_val = delta_w * nav
        price = prices.get(iid, 0.0)
        delta_shares = delta_val / price if price > 0 else 0.0

        weights.append(
            OptimizationWeight(
                instrument_id=iid,
                current_weight=_to_dec6(cur_w),
                target_weight=_to_dec6(tgt_w),
                delta_weight=_to_dec6(delta_w),
                delta_shares=_to_dec4(delta_shares),
                delta_value=_to_dec4(delta_val),
            )
        )

        # Generate order intent if delta is material (>0.5% weight)
        if abs(delta_w) > 0.005:
            side = "buy" if delta_w > 0 else "sell"
            intents.append(
                OrderIntent(
                    instrument_id=iid,
                    side=side,
                    quantity=abs(_to_dec4(delta_shares)),
                    estimated_value=abs(_to_dec4(delta_val)),
                    reason=f"{objective}: {cur_w:.1%} -> {tgt_w:.1%}",
                )
            )

    return OptimizationResult(
        portfolio_id=portfolio_id,
        objective=objective,
        expected_return=_to_dec6(exp_return),
        expected_risk=_to_dec6(exp_risk),
        sharpe_ratio=_to_dec4(sharpe) if sharpe is not None else None,
        weights=weights,
        order_intents=intents,
        calculated_at=datetime.now(UTC),
    )


def _min_variance(
    cov: np.ndarray,
    n: int,  # type: ignore[type-arg]
) -> np.ndarray:  # type: ignore[type-arg]
    """Analytical minimum variance portfolio (long-only)."""
    try:
        inv_cov = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        return np.ones(n) / n

    ones = np.ones(n)
    w = inv_cov @ ones
    w = w / w.sum()

    # Enforce long-only: clip negatives, renormalize
    w = np.maximum(w, 0)
    total = w.sum()
    return w / total if total > 1e-10 else np.ones(n) / n


def _max_sharpe(
    mu: np.ndarray,  # type: ignore[type-arg]
    cov: np.ndarray,  # type: ignore[type-arg]
    n: int,
    risk_free: float = 0.04,
) -> np.ndarray:  # type: ignore[type-arg]
    """Analytical maximum Sharpe ratio portfolio (long-only)."""
    try:
        inv_cov = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        return np.ones(n) / n

    excess = mu - risk_free
    w = inv_cov @ excess
    w = np.maximum(w, 0)
    total = w.sum()
    return w / total if total > 1e-10 else np.ones(n) / n


def _risk_parity(
    cov: np.ndarray,
    n: int,  # type: ignore[type-arg]
) -> np.ndarray:  # type: ignore[type-arg]
    """Naive risk parity: weight inversely proportional to volatility."""
    vols = np.sqrt(np.diag(cov))
    vols = np.maximum(vols, 1e-10)
    inv_vol = 1.0 / vols
    w = inv_vol / inv_vol.sum()
    return w


def _empty_result(portfolio_id: UUID, objective: OptimizationObjective) -> OptimizationResult:
    return OptimizationResult(
        portfolio_id=portfolio_id,
        objective=objective,
        expected_return=ZERO,
        expected_risk=ZERO,
        weights=[],
        order_intents=[],
        calculated_at=datetime.now(UTC),
    )
