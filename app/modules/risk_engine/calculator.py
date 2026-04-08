"""Stateless risk calculators — pure functions, no I/O.

Implements historical VaR, parametric VaR, stress testing,
and factor model decomposition using NumPy/SciPy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import numpy as np
from scipy import stats  # type: ignore[import-untyped]

from app.modules.risk_engine.interface import (
    FactorDecomposition,
    FactorExposure,
    LiquidityProfile,
    MarginSummary,
    PositionLiquidity,
    PositionMargin,
    RiskFactor,
    StressPositionImpact,
    StressScenario,
    StressTestResult,
    VaRContribution,
    VaRMethod,
    VaRResult,
)

ZERO = Decimal(0)
_Q4 = Decimal("0.0001")


def _to_dec(v: float) -> Decimal:
    if np.isnan(v) or np.isinf(v):
        return ZERO
    return Decimal(str(v)).quantize(_Q4)


# ---------------------------------------------------------------------------
# Historical VaR
# ---------------------------------------------------------------------------


def calculate_historical_var(
    portfolio_id: UUID,
    weights: dict[str, float],
    returns_matrix: np.ndarray,
    instrument_ids: list[str],
    confidence: float = 0.95,
    horizon_days: int = 1,
    nav: float = 1_000_000.0,
) -> VaRResult:
    """Calculate VaR using historical simulation.

    Args:
        weights: instrument_id -> portfolio weight
        returns_matrix: (n_days, n_instruments) array of historical returns
        instrument_ids: column labels for returns_matrix
        confidence: VaR confidence level (e.g. 0.95)
        horizon_days: holding period in days
        nav: current portfolio NAV for dollar VaR
    """
    n_days, n_instruments = returns_matrix.shape
    w = np.array([weights.get(iid, 0.0) for iid in instrument_ids])

    # Portfolio returns
    port_returns = returns_matrix @ w

    # Scale for horizon
    if horizon_days > 1:
        port_returns = port_returns * np.sqrt(horizon_days)

    # VaR = negative quantile of portfolio returns
    var_pct = float(-np.percentile(port_returns, (1 - confidence) * 100))
    var_amount = var_pct * nav

    # Expected shortfall (CVaR) = mean of losses beyond VaR
    tail = port_returns[port_returns <= -var_pct]
    es_pct = float(-tail.mean()) if len(tail) > 0 else var_pct
    es_amount = es_pct * nav

    # Component VaR contributions
    contributions = _component_var(w, returns_matrix, instrument_ids, var_pct, nav)

    return VaRResult(
        portfolio_id=portfolio_id,
        method=VaRMethod.HISTORICAL,
        confidence_level=confidence,
        horizon_days=horizon_days,
        var_amount=_to_dec(var_amount),
        var_pct=_to_dec(var_pct),
        expected_shortfall=_to_dec(es_amount),
        contributions=contributions,
        calculated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Parametric VaR (variance-covariance)
# ---------------------------------------------------------------------------


def calculate_parametric_var(
    portfolio_id: UUID,
    weights: dict[str, float],
    returns_matrix: np.ndarray,
    instrument_ids: list[str],
    confidence: float = 0.95,
    horizon_days: int = 1,
    nav: float = 1_000_000.0,
) -> VaRResult:
    """Calculate VaR using variance-covariance (parametric) method.

    Assumes returns are normally distributed.
    """
    w = np.array([weights.get(iid, 0.0) for iid in instrument_ids])

    # Covariance matrix from historical returns
    cov = np.cov(returns_matrix.T)
    if cov.ndim == 0:
        cov = np.array([[float(cov)]])

    # Portfolio variance and std dev
    port_var = float(w @ cov @ w)
    port_std = np.sqrt(port_var)

    # Z-score for confidence level
    z = stats.norm.ppf(confidence)

    # Scale for horizon
    var_pct = float(z * port_std * np.sqrt(horizon_days))
    var_amount = var_pct * nav

    # Parametric ES (assuming normal)
    es_z = float(stats.norm.pdf(z) / (1 - confidence))
    es_pct = float(es_z * port_std * np.sqrt(horizon_days))
    es_amount = es_pct * nav

    contributions = _component_var(w, returns_matrix, instrument_ids, var_pct, nav)

    return VaRResult(
        portfolio_id=portfolio_id,
        method=VaRMethod.PARAMETRIC,
        confidence_level=confidence,
        horizon_days=horizon_days,
        var_amount=_to_dec(var_amount),
        var_pct=_to_dec(var_pct),
        expected_shortfall=_to_dec(es_amount),
        contributions=contributions,
        calculated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Component VaR
# ---------------------------------------------------------------------------


def _component_var(
    weights: np.ndarray,
    returns_matrix: np.ndarray,
    instrument_ids: list[str],
    portfolio_var_pct: float,
    nav: float,
) -> list[VaRContribution]:
    """Calculate marginal and component VaR for each instrument."""
    cov = np.cov(returns_matrix.T)
    if cov.ndim == 0:
        cov = np.array([[float(cov)]])

    port_vol = np.sqrt(float(weights @ cov @ weights))
    if port_vol < 1e-10:
        return []

    # Marginal VaR = (Cov @ w) / portfolio_vol
    marginal = (cov @ weights) / port_vol

    contributions: list[VaRContribution] = []
    total_component = 0.0

    for i, _iid in enumerate(instrument_ids):
        w_i = float(weights[i])
        if abs(w_i) < 1e-10:
            continue
        m_var = float(marginal[i])
        c_var = w_i * m_var
        total_component += c_var

    # Normalize so component VaRs sum to portfolio VaR
    for i, iid in enumerate(instrument_ids):
        w_i = float(weights[i])
        if abs(w_i) < 1e-10:
            continue
        m_var = float(marginal[i])
        c_var = w_i * m_var
        pct = c_var / total_component if abs(total_component) > 1e-10 else 0.0

        contributions.append(
            VaRContribution(
                instrument_id=iid,
                weight=_to_dec(w_i),
                marginal_var=_to_dec(m_var * nav),
                component_var=_to_dec(c_var / total_component * portfolio_var_pct * nav)
                if abs(total_component) > 1e-10
                else ZERO,
                pct_contribution=_to_dec(pct),
            )
        )

    return contributions


# ---------------------------------------------------------------------------
# Stress testing
# ---------------------------------------------------------------------------


def run_stress_test(
    portfolio_id: UUID,
    scenario: StressScenario,
    positions: dict[str, tuple[Decimal, str | None]],
    nav: float,
) -> StressTestResult:
    """Apply stress scenario shocks to portfolio positions.

    Args:
        positions: instrument_id -> (market_value, sector)
        nav: current NAV for percentage calculations
    """
    total_impact = Decimal(0)
    impacts: list[StressPositionImpact] = []

    for iid, (market_value, sector) in positions.items():
        shock = _resolve_shock(scenario.shocks, iid, sector)
        current = market_value
        stressed = current * (1 + Decimal(str(shock)))
        pnl = stressed - current
        pct = Decimal(str(shock))

        total_impact += pnl
        impacts.append(
            StressPositionImpact(
                instrument_id=iid,
                current_value=current,
                stressed_value=stressed.quantize(_Q4),
                pnl_impact=pnl.quantize(_Q4),
                pct_change=pct.quantize(_Q4),
            )
        )

    total_pct = _to_dec(float(total_impact) / nav) if nav > 0 else ZERO

    return StressTestResult(
        portfolio_id=portfolio_id,
        scenario_name=scenario.name,
        scenario_type=scenario.scenario_type,
        total_pnl_impact=total_impact.quantize(_Q4),
        total_pct_change=total_pct,
        position_impacts=impacts,
        calculated_at=datetime.now(UTC),
    )


def _resolve_shock(
    shocks: dict[str, float],
    instrument_id: str,
    sector: str | None,
) -> float:
    """Resolve the shock magnitude for an instrument.

    Priority: instrument-specific > sector > market > 0.
    """
    if instrument_id in shocks:
        return shocks[instrument_id]
    if sector and sector in shocks:
        return shocks[sector]
    return shocks.get("market", 0.0)


# ---------------------------------------------------------------------------
# Factor model decomposition
# ---------------------------------------------------------------------------


def calculate_factor_decomposition(
    portfolio_id: UUID,
    weights: dict[str, float],
    returns_matrix: np.ndarray,
    instrument_ids: list[str],
    sector_map: dict[str, str],
    nav: float,
    currency_map: dict[str, str] | None = None,
    base_currency: str = "USD",
) -> FactorDecomposition:
    """Decompose portfolio risk into market, sector, currency, and idiosyncratic.

    Uses a simple factor model:
    r_i = beta_market * r_market + beta_sector * r_sector
          + beta_ccy * r_ccy + epsilon_i
    """
    n_days, n_instruments = returns_matrix.shape
    w = np.array([weights.get(iid, 0.0) for iid in instrument_ids])

    # Market factor = equal-weighted average return
    market_returns = returns_matrix.mean(axis=1)
    market_var = float(np.var(market_returns))

    # Portfolio returns
    port_returns = returns_matrix @ w
    port_var = float(np.var(port_returns))

    if port_var < 1e-12:
        return FactorDecomposition(
            portfolio_id=portfolio_id,
            total_risk=ZERO,
            systematic_risk=ZERO,
            idiosyncratic_risk=ZERO,
            systematic_pct=ZERO,
            factor_exposures=[],
            calculated_at=datetime.now(UTC),
        )

    # Market beta for portfolio
    market_cov = float(np.cov(port_returns, market_returns)[0, 1])
    market_beta = market_cov / market_var if market_var > 1e-12 else 0.0

    # Systematic variance from market factor
    systematic_var_market = market_beta**2 * market_var

    # Sector factors
    sectors = sorted(set(sector_map.values()))
    sector_exposures: list[FactorExposure] = []

    # Market factor exposure
    market_exposure_value = market_beta * nav * np.sqrt(market_var) * np.sqrt(252)
    sector_systematic_var = 0.0

    for sector_name in sectors:
        sector_ids = [iid for iid in instrument_ids if sector_map.get(iid) == sector_name]
        if not sector_ids:
            continue

        sector_indices = [instrument_ids.index(iid) for iid in sector_ids]
        sector_returns = returns_matrix[:, sector_indices].mean(axis=1)

        # Residual sector returns (orthogonal to market)
        s_var = float(np.var(sector_returns))
        if s_var < 1e-12:
            continue

        s_cov = float(np.cov(port_returns, sector_returns)[0, 1])
        s_beta = s_cov / s_var if s_var > 1e-12 else 0.0
        s_contrib = s_beta**2 * s_var
        sector_systematic_var += s_contrib

        sector_exposures.append(
            FactorExposure(
                factor=RiskFactor.SECTOR,
                factor_name=sector_name,
                beta=_to_dec(s_beta),
                exposure_value=_to_dec(s_beta * nav * np.sqrt(s_var) * np.sqrt(252)),
                pct_of_total=_to_dec(s_contrib / port_var) if port_var > 1e-12 else ZERO,
            )
        )

    # Currency factors — one per non-base currency
    currency_exposures: list[FactorExposure] = []
    currency_systematic_var = 0.0

    if currency_map:
        currencies = sorted({ccy for ccy in currency_map.values() if ccy != base_currency})
        for ccy in currencies:
            ccy_ids = [iid for iid in instrument_ids if currency_map.get(iid) == ccy]
            if not ccy_ids:
                continue
            ccy_indices = [instrument_ids.index(iid) for iid in ccy_ids]
            # Currency factor return = average return of positions in that currency
            ccy_returns = returns_matrix[:, ccy_indices].mean(axis=1)
            c_var = float(np.var(ccy_returns))
            if c_var < 1e-12:
                continue
            c_cov = float(np.cov(port_returns, ccy_returns)[0, 1])
            c_beta = c_cov / c_var
            c_contrib = c_beta**2 * c_var
            currency_systematic_var += c_contrib

            currency_exposures.append(
                FactorExposure(
                    factor=RiskFactor.CURRENCY,
                    factor_name=ccy,
                    beta=_to_dec(c_beta),
                    exposure_value=_to_dec(c_beta * nav * np.sqrt(c_var) * np.sqrt(252)),
                    pct_of_total=_to_dec(c_contrib / port_var) if port_var > 1e-12 else ZERO,
                )
            )

    total_systematic = max(
        systematic_var_market + sector_systematic_var + currency_systematic_var, 0.0
    )
    idiosyncratic_var = max(port_var - total_systematic, 0.0)

    total_risk = _to_dec(np.sqrt(port_var) * np.sqrt(252) * nav)
    systematic_risk = _to_dec(np.sqrt(total_systematic) * np.sqrt(252) * nav)
    idio_risk = _to_dec(np.sqrt(idiosyncratic_var) * np.sqrt(252) * nav)
    sys_pct = _to_dec(total_systematic / port_var) if port_var > 1e-12 else ZERO

    all_exposures = [
        FactorExposure(
            factor=RiskFactor.MARKET,
            factor_name="Market",
            beta=_to_dec(market_beta),
            exposure_value=_to_dec(float(market_exposure_value)),
            pct_of_total=_to_dec(systematic_var_market / port_var) if port_var > 1e-12 else ZERO,
        ),
        *sector_exposures,
        *currency_exposures,
        FactorExposure(
            factor=RiskFactor.IDIOSYNCRATIC,
            factor_name="Idiosyncratic",
            beta=ZERO,
            exposure_value=idio_risk,
            pct_of_total=_to_dec(idiosyncratic_var / port_var) if port_var > 1e-12 else ZERO,
        ),
    ]

    return FactorDecomposition(
        portfolio_id=portfolio_id,
        total_risk=total_risk,
        systematic_risk=systematic_risk,
        idiosyncratic_risk=idio_risk,
        systematic_pct=sys_pct,
        factor_exposures=all_exposures,
        calculated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# 3B. Liquidity Risk — pure functions
# ---------------------------------------------------------------------------

# Default margin rates by asset class
_MARGIN_RATES: dict[str, float] = {
    "equity": 0.50,
    "fixed_income": 0.10,
    "fx": 0.03,
    "commodity": 0.15,
    "option": 1.00,
    "default": 0.50,
}

# Participation rate: max fraction of ADV we can trade per day
_PARTICIPATION_RATE = 0.20  # 20% of ADV


def calculate_liquidity_profile(
    *,
    portfolio_id: UUID,
    positions: list[tuple[str, Decimal, Decimal]],  # (instrument_id, market_value, adv_usd)
    total_nav: Decimal,
    business_date: datetime,
    pending_redemptions: Decimal = ZERO,
) -> tuple[LiquidityProfile, list[PositionLiquidity]]:
    """Compute portfolio liquidity bucketing.

    For each position, estimate days to liquidate at the participation rate.
    Then bucket by: 1 day, 1 week, 1 month, 3 months, illiquid.
    """
    details: list[PositionLiquidity] = []
    buckets = {"1d": ZERO, "1w": ZERO, "1m": ZERO, "3m": ZERO, "illiquid": ZERO}

    for inst_id, mv, adv in positions:
        abs_mv = abs(mv)
        if adv > 0:
            daily_capacity = adv * Decimal(str(_PARTICIPATION_RATE))
            days = abs_mv / daily_capacity if daily_capacity > 0 else Decimal(999)
        else:
            days = Decimal(999)

        if days <= 1:
            bucket = "1d"
        elif days <= 5:
            bucket = "1w"
        elif days <= 21:
            bucket = "1m"
        elif days <= 63:
            bucket = "3m"
        else:
            bucket = "illiquid"

        buckets[bucket] += abs_mv
        pct = abs_mv / total_nav if total_nav > 0 else ZERO
        details.append(
            PositionLiquidity(
                instrument_id=inst_id,
                market_value=mv,
                avg_daily_volume_usd=adv,
                days_to_liquidate=days.quantize(_Q4),
                liquidity_bucket=bucket,
                pct_of_nav=pct.quantize(_Q4),
            )
        )

    total_abs = sum(buckets.values())
    pct_fn = lambda v: (v / total_abs).quantize(_Q4) if total_abs > 0 else ZERO  # noqa: E731

    # Weighted days to liquidate
    if total_abs > 0:
        w_days = sum(
            d.days_to_liquidate * abs(d.market_value) / total_abs for d in details
        ).quantize(Decimal("0.01"))
    else:
        w_days = ZERO

    # Redemption coverage: what fraction of pending redemptions can be met
    # by liquidating positions within 1 week
    liquid_1w = buckets["1d"] + buckets["1w"]
    red_cov = (
        min(liquid_1w / pending_redemptions, Decimal(1)) if pending_redemptions > 0 else Decimal(1)
    ).quantize(_Q4)

    profile = LiquidityProfile(
        portfolio_id=portfolio_id,
        business_date=business_date,
        total_nav=total_nav,
        pct_1_day=pct_fn(buckets["1d"]),
        pct_1_week=pct_fn(buckets["1w"]),
        pct_1_month=pct_fn(buckets["1m"]),
        pct_3_months=pct_fn(buckets["3m"]),
        pct_illiquid=pct_fn(buckets["illiquid"]),
        weighted_days_to_liquidate=w_days,
        redemption_coverage_pct=red_cov,
    )
    return profile, details


# ---------------------------------------------------------------------------
# 3C. Margin Management — pure functions
# ---------------------------------------------------------------------------


def calculate_margin_requirements(
    *,
    portfolio_id: UUID,
    positions: list[tuple[str, Decimal, str]],  # (instrument_id, market_value, asset_class)
    cash_balance: Decimal,
    business_date: datetime,
) -> tuple[MarginSummary, list[PositionMargin]]:
    """Compute portfolio margin requirements from position values and margin rates."""
    pos_margins: list[PositionMargin] = []
    total_initial = ZERO
    total_maintenance = ZERO

    for inst_id, mv, asset_class in positions:
        rate = Decimal(str(_MARGIN_RATES.get(asset_class, _MARGIN_RATES["default"])))
        initial = (abs(mv) * rate).quantize(Decimal("0.01"))
        maint = (initial * Decimal("0.75")).quantize(Decimal("0.01"))  # 75% of initial
        total_initial += initial
        total_maintenance += maint
        pos_margins.append(
            PositionMargin(
                instrument_id=inst_id,
                market_value=mv,
                margin_rate=rate,
                initial_margin=initial,
                maintenance_margin=maint,
            )
        )

    excess = cash_balance - total_initial
    util = (total_initial / cash_balance).quantize(_Q4) if cash_balance > 0 else Decimal(999)
    margin_call = excess < 0

    summary = MarginSummary(
        portfolio_id=portfolio_id,
        business_date=business_date,
        initial_margin=total_initial,
        maintenance_margin=total_maintenance,
        margin_available=cash_balance,
        margin_excess_deficit=excess,
        margin_utilization_pct=util,
        margin_call_triggered=margin_call,
    )
    return summary, pos_margins
