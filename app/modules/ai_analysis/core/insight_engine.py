"""Portfolio insight generator — pure rules-based analysis (no LLM needed)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.ai_analysis.interfaces import PortfolioInsight

ZERO = Decimal(0)


def generate_portfolio_insights(
    positions: list[dict],
    risk_metrics: dict | None = None,
    factor_exposures: dict | None = None,
) -> list[PortfolioInsight]:
    """Generate actionable portfolio insights from position data.

    Each position dict should contain at minimum:
        instrument_id, quantity, market_value, sector
    Optional fields: asset_class, currency, factor_exposures
    """
    insights: list[PortfolioInsight] = []

    if not positions:
        return insights

    total_value = sum(Decimal(str(p.get("market_value", 0))) for p in positions)
    if total_value <= ZERO:
        return insights

    insights.extend(_check_position_concentration(positions, total_value))
    insights.extend(_check_sector_concentration(positions, total_value))
    insights.extend(_check_small_positions(positions, total_value))
    insights.extend(_check_sector_correlation(positions))
    insights.extend(_check_cash_drag(positions, total_value))
    insights.extend(_check_factor_tilts(factor_exposures))

    return insights


def _check_position_concentration(
    positions: list[dict], total_value: Decimal
) -> list[PortfolioInsight]:
    """Flag any single position > 10% of portfolio."""
    insights: list[PortfolioInsight] = []
    for pos in positions:
        mv = Decimal(str(pos.get("market_value", 0)))
        weight = mv / total_value if total_value > ZERO else ZERO
        if weight > Decimal("0.10"):
            pct = round(float(weight) * 100, 1)
            insights.append(
                PortfolioInsight(
                    insight_type="concentration_risk",
                    severity="warning",
                    title=f"High concentration in {pos.get('instrument_id', 'unknown')}",
                    description=(
                        f"Position represents {pct}% of portfolio, "
                        f"exceeding the 10% single-name concentration guideline."
                    ),
                    affected_instruments=[pos.get("instrument_id", "unknown")],
                    suggested_action="Consider trimming the position or adding hedges.",
                )
            )
    return insights


def _check_sector_concentration(
    positions: list[dict], total_value: Decimal
) -> list[PortfolioInsight]:
    """Flag any sector > 30% of portfolio."""
    sector_values: dict[str, Decimal] = {}
    sector_instruments: dict[str, list[str]] = {}
    for pos in positions:
        sector = pos.get("sector", "unknown")
        mv = Decimal(str(pos.get("market_value", 0)))
        sector_values[sector] = sector_values.get(sector, ZERO) + mv
        sector_instruments.setdefault(sector, []).append(pos.get("instrument_id", "unknown"))

    insights: list[PortfolioInsight] = []
    for sector, value in sector_values.items():
        weight = value / total_value if total_value > ZERO else ZERO
        if weight > Decimal("0.30"):
            pct = round(float(weight) * 100, 1)
            insights.append(
                PortfolioInsight(
                    insight_type="sector_concentration",
                    severity="warning",
                    title=f"Sector overweight: {sector}",
                    description=(
                        f"{sector} represents {pct}% of portfolio, "
                        f"exceeding the 30% sector concentration guideline."
                    ),
                    affected_instruments=sector_instruments.get(sector, []),
                    suggested_action=(f"Diversify away from {sector} into underweight sectors."),
                )
            )
    return insights


def _check_small_positions(positions: list[dict], total_value: Decimal) -> list[PortfolioInsight]:
    """Flag positions < 0.5% of portfolio as cleanup candidates."""
    small: list[str] = []
    for pos in positions:
        mv = Decimal(str(pos.get("market_value", 0)))
        weight = mv / total_value if total_value > ZERO else ZERO
        if ZERO < weight < Decimal("0.005"):
            small.append(pos.get("instrument_id", "unknown"))

    if small:
        return [
            PortfolioInsight(
                insight_type="small_position_cleanup",
                severity="info",
                title=f"{len(small)} small position(s) below 0.5%",
                description=(
                    "These positions contribute minimal alpha but add "
                    "operational complexity and transaction costs."
                ),
                affected_instruments=small,
                suggested_action=("Consider closing or consolidating small positions."),
            )
        ]
    return []


def _check_sector_correlation(positions: list[dict]) -> list[PortfolioInsight]:
    """Warn if top 5 positions by market value are in the same sector."""
    sorted_pos = sorted(
        positions,
        key=lambda p: Decimal(str(p.get("market_value", 0))),
        reverse=True,
    )
    top5 = sorted_pos[:5]
    if len(top5) < 5:
        return []

    sectors = [p.get("sector", "unknown") for p in top5]
    unique_sectors = set(sectors)
    if len(unique_sectors) == 1 and "unknown" not in unique_sectors:
        sector = next(iter(unique_sectors))
        return [
            PortfolioInsight(
                insight_type="high_correlation",
                severity="critical",
                title=f"Top 5 positions all in {sector}",
                description=(
                    "The five largest positions are concentrated in a single "
                    "sector, creating high correlation risk and reducing "
                    "portfolio diversification."
                ),
                affected_instruments=[p.get("instrument_id", "unknown") for p in top5],
                suggested_action=("Urgently diversify across sectors to reduce correlation risk."),
            )
        ]
    return []


def _check_cash_drag(positions: list[dict], total_value: Decimal) -> list[PortfolioInsight]:
    """Flag cash > 15% of portfolio as potential drag on returns."""
    cash_value = ZERO
    for pos in positions:
        asset_class = pos.get("asset_class", "").lower()
        sector = pos.get("sector", "").lower()
        if asset_class == "cash" or sector == "cash":
            cash_value += Decimal(str(pos.get("market_value", 0)))

    if total_value > ZERO:
        cash_pct = cash_value / total_value
        if cash_pct > Decimal("0.15"):
            pct = round(float(cash_pct) * 100, 1)
            return [
                PortfolioInsight(
                    insight_type="cash_drag",
                    severity="info",
                    title=f"Elevated cash position ({pct}%)",
                    description=(
                        f"Cash represents {pct}% of the portfolio, "
                        f"which may create a drag on returns relative "
                        f"to the benchmark."
                    ),
                    suggested_action=(
                        "Deploy excess cash into short-duration instruments "
                        "or increase equity exposure if market conditions warrant."
                    ),
                )
            ]
    return []


def _check_factor_tilts(
    factor_exposures: dict | None,
) -> list[PortfolioInsight]:
    """Warn if any factor z-score exceeds 2.0."""
    if not factor_exposures:
        return []

    insights: list[PortfolioInsight] = []
    for factor_name, z_score in factor_exposures.items():
        try:
            z = float(z_score)
        except (TypeError, ValueError):
            continue
        if abs(z) > 2.0:
            direction = "long" if z > 0 else "short"
            insights.append(
                PortfolioInsight(
                    insight_type="factor_tilt",
                    severity="warning",
                    title=f"Extreme {factor_name} factor tilt",
                    description=(
                        f"The portfolio has a {direction} {factor_name} factor "
                        f"z-score of {z:.2f}, which exceeds the +/-2.0 threshold "
                        f"and may indicate unintended factor exposure."
                    ),
                    suggested_action=(
                        f"Review positions contributing to the {factor_name} "
                        f"factor tilt and consider rebalancing."
                    ),
                )
            )
    return insights
