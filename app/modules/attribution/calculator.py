"""Stateless attribution calculators — pure functions, no I/O.

Implements Brinson-Fachler attribution and risk-based P&L decomposition.
Carino geometric linking for multi-period returns.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import numpy as np

from app.modules.attribution.interface import (
    BrinsonFachlerResult,
    CumulativeAttribution,
    RiskBasedResult,
    RiskFactorAttribution,
    SectorAttribution,
)

ZERO = Decimal(0)
_Q6 = Decimal("0.000001")
_Q4 = Decimal("0.0001")


def _to_dec6(v: float) -> Decimal:
    return Decimal(str(v)).quantize(_Q6)


def _to_dec4(v: float) -> Decimal:
    return Decimal(str(v)).quantize(_Q4)


# ---------------------------------------------------------------------------
# Brinson-Fachler
# ---------------------------------------------------------------------------


def calculate_brinson_fachler(
    portfolio_id: UUID,
    period_start: date,
    period_end: date,
    portfolio_weights: dict[str, float],
    benchmark_weights: dict[str, float],
    portfolio_returns: dict[str, float],
    benchmark_returns: dict[str, float],
    sector_map: dict[str, str],
) -> BrinsonFachlerResult:
    """Calculate Brinson-Fachler attribution by sector.

    Args:
        portfolio_weights: instrument_id -> weight in portfolio
        benchmark_weights: instrument_id -> weight in benchmark
        portfolio_returns: instrument_id -> return over period
        benchmark_returns: instrument_id -> return over period
        sector_map: instrument_id -> sector name
    """
    # Aggregate to sector level
    sectors = sorted(set(sector_map.values()))

    # Portfolio total return
    port_return = sum(
        portfolio_weights.get(iid, 0.0) * portfolio_returns.get(iid, 0.0)
        for iid in set(portfolio_weights) | set(benchmark_weights)
    )
    bench_return = sum(
        benchmark_weights.get(iid, 0.0) * benchmark_returns.get(iid, 0.0)
        for iid in set(portfolio_weights) | set(benchmark_weights)
    )

    sector_results: list[SectorAttribution] = []
    total_allocation = 0.0
    total_selection = 0.0
    total_interaction = 0.0

    for sector in sectors:
        sector_ids = [iid for iid, s in sector_map.items() if s == sector]
        if not sector_ids:
            continue

        # Sector weights
        pw = sum(portfolio_weights.get(iid, 0.0) for iid in sector_ids)
        bw = sum(benchmark_weights.get(iid, 0.0) for iid in sector_ids)

        # Sector returns (weighted average within sector)
        pr = (
            sum(
                portfolio_weights.get(iid, 0.0) * portfolio_returns.get(iid, 0.0)
                for iid in sector_ids
            )
            / pw
            if pw > 1e-10
            else 0.0
        )
        br = (
            sum(
                benchmark_weights.get(iid, 0.0) * benchmark_returns.get(iid, 0.0)
                for iid in sector_ids
            )
            / bw
            if bw > 1e-10
            else 0.0
        )

        # Brinson-Fachler effects
        allocation = (pw - bw) * (br - bench_return)
        selection = bw * (pr - br)
        interaction = (pw - bw) * (pr - br)
        total = allocation + selection + interaction

        total_allocation += allocation
        total_selection += selection
        total_interaction += interaction

        sector_results.append(
            SectorAttribution(
                sector=sector,
                portfolio_weight=_to_dec6(pw),
                benchmark_weight=_to_dec6(bw),
                portfolio_return=_to_dec6(pr),
                benchmark_return=_to_dec6(br),
                allocation_effect=_to_dec6(allocation),
                selection_effect=_to_dec6(selection),
                interaction_effect=_to_dec6(interaction),
                total_effect=_to_dec6(total),
            )
        )

    return BrinsonFachlerResult(
        portfolio_id=portfolio_id,
        period_start=period_start,
        period_end=period_end,
        portfolio_return=_to_dec6(port_return),
        benchmark_return=_to_dec6(bench_return),
        active_return=_to_dec6(port_return - bench_return),
        total_allocation=_to_dec6(total_allocation),
        total_selection=_to_dec6(total_selection),
        total_interaction=_to_dec6(total_interaction),
        sectors=sector_results,
        calculated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Risk-based P&L attribution
# ---------------------------------------------------------------------------


def calculate_risk_based_attribution(
    portfolio_id: UUID,
    period_start: date,
    period_end: date,
    weights: dict[str, float],
    returns_matrix: np.ndarray,  # type: ignore[type-arg]
    instrument_ids: list[str],
    sector_map: dict[str, str],
    nav: float,
) -> RiskBasedResult:
    """Decompose P&L into systematic (market + sector) and idiosyncratic.

    Uses a simple factor model regression approach.
    """
    n_days, n_instruments = returns_matrix.shape
    w = np.array([weights.get(iid, 0.0) for iid in instrument_ids])

    # Portfolio returns
    port_returns = returns_matrix @ w
    total_pnl = float(port_returns.sum()) * nav

    # Market factor
    market_returns = returns_matrix.mean(axis=1)
    market_var = float(np.var(market_returns))

    factor_contributions: list[RiskFactorAttribution] = []

    # Market contribution
    if market_var > 1e-12:
        market_cov = float(np.cov(port_returns, market_returns)[0, 1])
        market_beta = market_cov / market_var
        market_pnl = float(market_beta * market_returns.sum()) * nav
    else:
        market_beta = 0.0
        market_pnl = 0.0

    factor_contributions.append(
        RiskFactorAttribution(
            factor="Market",
            factor_return=_to_dec6(float(market_returns.sum())),
            portfolio_exposure=_to_dec6(market_beta),
            pnl_contribution=_to_dec4(market_pnl),
            pct_of_total=_to_dec6(market_pnl / total_pnl) if abs(total_pnl) > 1e-10 else ZERO,
        )
    )

    # Sector contributions
    sectors = sorted(set(sector_map.values()))
    sector_pnl_total = 0.0

    for sector in sectors:
        sector_ids = [iid for iid in instrument_ids if sector_map.get(iid) == sector]
        if not sector_ids:
            continue

        sector_indices = [instrument_ids.index(iid) for iid in sector_ids]
        sector_returns = returns_matrix[:, sector_indices].mean(axis=1)
        s_var = float(np.var(sector_returns))

        if s_var < 1e-12:
            continue

        s_cov = float(np.cov(port_returns, sector_returns)[0, 1])
        s_beta = s_cov / s_var
        s_pnl = float(s_beta * sector_returns.sum()) * nav
        sector_pnl_total += s_pnl

        factor_contributions.append(
            RiskFactorAttribution(
                factor=sector,
                factor_return=_to_dec6(float(sector_returns.sum())),
                portfolio_exposure=_to_dec6(s_beta),
                pnl_contribution=_to_dec4(s_pnl),
                pct_of_total=_to_dec6(s_pnl / total_pnl) if abs(total_pnl) > 1e-10 else ZERO,
            )
        )

    systematic_pnl = market_pnl + sector_pnl_total
    idiosyncratic_pnl = total_pnl - systematic_pnl

    factor_contributions.append(
        RiskFactorAttribution(
            factor="Idiosyncratic",
            factor_return=ZERO,
            portfolio_exposure=ZERO,
            pnl_contribution=_to_dec4(idiosyncratic_pnl),
            pct_of_total=_to_dec6(idiosyncratic_pnl / total_pnl)
            if abs(total_pnl) > 1e-10
            else ZERO,
        )
    )

    return RiskBasedResult(
        portfolio_id=portfolio_id,
        period_start=period_start,
        period_end=period_end,
        total_pnl=_to_dec4(total_pnl),
        systematic_pnl=_to_dec4(systematic_pnl),
        idiosyncratic_pnl=_to_dec4(idiosyncratic_pnl),
        systematic_pct=_to_dec6(systematic_pnl / total_pnl) if abs(total_pnl) > 1e-10 else ZERO,
        factor_contributions=factor_contributions,
        calculated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Carino geometric linking
# ---------------------------------------------------------------------------


def _carino_factor(r: float) -> float:
    """Carino smoothing factor: ln(1+r) / r when r != 0."""
    if abs(r) < 1e-12:
        return 1.0
    return math.log(1 + r) / r


def link_multi_period(
    portfolio_id: UUID,
    period_start: date,
    period_end: date,
    period_results: list[BrinsonFachlerResult],
) -> CumulativeAttribution:
    """Link single-period Brinson-Fachler results using Carino method.

    Ensures allocation + selection + interaction = active return
    over multiple periods with geometric compounding.
    """
    if not period_results:
        return CumulativeAttribution(
            portfolio_id=portfolio_id,
            period_start=period_start,
            period_end=period_end,
            cumulative_portfolio_return=ZERO,
            cumulative_benchmark_return=ZERO,
            cumulative_active_return=ZERO,
            cumulative_allocation=ZERO,
            cumulative_selection=ZERO,
            cumulative_interaction=ZERO,
            periods=[],
            calculated_at=datetime.now(UTC),
        )

    # Compound returns
    cum_port = 1.0
    cum_bench = 1.0
    for p in period_results:
        cum_port *= 1 + float(p.portfolio_return)
        cum_bench *= 1 + float(p.benchmark_return)
    cum_port -= 1
    cum_bench -= 1
    cum_active = cum_port - cum_bench

    # Carino linking factors
    k_total = _carino_factor(cum_port)

    cum_allocation = 0.0
    cum_selection = 0.0
    cum_interaction = 0.0

    for p in period_results:
        rp = float(p.portfolio_return)
        k_t = _carino_factor(rp)
        scale = k_t / k_total if abs(k_total) > 1e-12 else 1.0

        cum_allocation += float(p.total_allocation) * scale
        cum_selection += float(p.total_selection) * scale
        cum_interaction += float(p.total_interaction) * scale

    return CumulativeAttribution(
        portfolio_id=portfolio_id,
        period_start=period_start,
        period_end=period_end,
        cumulative_portfolio_return=_to_dec6(cum_port),
        cumulative_benchmark_return=_to_dec6(cum_bench),
        cumulative_active_return=_to_dec6(cum_active),
        cumulative_allocation=_to_dec6(cum_allocation),
        cumulative_selection=_to_dec6(cum_selection),
        cumulative_interaction=_to_dec6(cum_interaction),
        periods=period_results,
        calculated_at=datetime.now(UTC),
    )
