"""Trade cost estimation model.

Estimates the total cost of executing a hypothetical trade, broken down into
commission, spread, and market impact components. Used by the alpha engine
to assess implementation shortfall in what-if and optimization scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal(0)
_Q8 = Decimal("0.00000001")


@dataclass(frozen=True)
class TradeCostBreakdown:
    """Itemised cost estimate for a single trade."""

    commission: Decimal
    spread_cost: Decimal
    market_impact: Decimal

    @property
    def total(self) -> Decimal:
        return self.commission + self.spread_cost + self.market_impact

    @property
    def total_bps(self) -> Decimal:
        """Total cost in basis points relative to notional, if notional > 0."""
        return self.commission + self.spread_cost + self.market_impact


class TradeCostModel:
    """Simple linear cost model parameterised by bps and impact coefficient.

    Parameters:
        commission_bps: commission as basis points of notional (e.g. 5 = 0.05%)
        spread_bps: half-spread as basis points of notional
        impact_coefficient: market impact coefficient — impact = coeff * sqrt(notional / adv)
    """

    def __init__(
        self,
        *,
        commission_bps: Decimal = Decimal("5"),
        spread_bps: Decimal = Decimal("3"),
        impact_coefficient: Decimal = Decimal("0.1"),
    ) -> None:
        self.commission_bps = commission_bps
        self.spread_bps = spread_bps
        self.impact_coefficient = impact_coefficient

    def estimate(
        self,
        notional: Decimal,
        *,
        adv: Decimal | None = None,
    ) -> TradeCostBreakdown:
        """Estimate trade cost for a given notional value.

        Args:
            notional: absolute trade notional in base currency
            adv: average daily volume in base currency (for market impact).
                 If None, market impact is estimated as zero.

        Returns:
            Itemised cost breakdown with commission, spread, and impact.
        """
        abs_notional = abs(notional)
        bps_divisor = Decimal("10000")

        commission = (abs_notional * self.commission_bps / bps_divisor).quantize(_Q8)
        spread_cost = (abs_notional * self.spread_bps / bps_divisor).quantize(_Q8)

        if adv and adv > 0:
            # Square-root market impact model: impact = coeff * sqrt(participation_rate)
            participation = float(abs_notional / adv)
            impact_pct = self.impact_coefficient * Decimal(str(participation**0.5))
            market_impact = (abs_notional * impact_pct).quantize(_Q8)
        else:
            market_impact = ZERO

        return TradeCostBreakdown(
            commission=commission,
            spread_cost=spread_cost,
            market_impact=market_impact,
        )
