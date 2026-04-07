"""Market impact model — Almgren-Chriss square-root formula.

Calculates temporary and permanent market impact based on order size
relative to average daily volume. The permanent component feeds back
into the GBM simulator so subsequent price ticks reflect the impact.

Model: impact_bps = eta * daily_vol * sqrt(quantity / ADV)

References:
- Almgren & Chriss (2000), "Optimal execution of portfolio transactions"
- Kissell & Glantz (2003), "Optimal Trading Strategies"
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ImpactEstimate:
    """Estimated market impact breakdown."""
    temporary_bps: float
    permanent_bps: float
    total_bps: float


class MarketImpactModel:
    """Calculates and applies market impact using the square-root model."""

    def __init__(
        self,
        eta: float = 0.6,
        temporary_fraction: float = 0.6,
    ) -> None:
        self._eta = eta
        self._temporary_fraction = temporary_fraction

    def estimate_impact(
        self,
        quantity: int,
        adv: int,
        daily_volatility: float,
        side: str,
    ) -> ImpactEstimate:
        """Estimate temporary and permanent impact in basis points.

        Args:
            quantity: Order size in shares
            adv: Average daily volume in shares
            daily_volatility: Annualized volatility (will be converted to daily)
            side: "buy" or "sell"
        """
        if adv <= 0 or quantity <= 0:
            return ImpactEstimate(temporary_bps=0.0, permanent_bps=0.0, total_bps=0.0)

        # Convert annual vol to daily: sigma_daily = sigma_annual / sqrt(252)
        daily_vol = daily_volatility / math.sqrt(252)

        # Square-root model: total impact = eta * sigma_daily * sqrt(Q / ADV)
        participation = quantity / adv
        total_bps = self._eta * daily_vol * math.sqrt(participation) * 10_000

        temporary_bps = total_bps * self._temporary_fraction
        permanent_bps = total_bps * (1.0 - self._temporary_fraction)

        return ImpactEstimate(
            temporary_bps=temporary_bps,
            permanent_bps=permanent_bps,
            total_bps=total_bps,
        )

    def apply_permanent_impact(
        self,
        current_price: Decimal,
        impact_bps: float,
        side: str,
    ) -> Decimal:
        """Compute new price after permanent impact.

        Buy orders push price up, sell orders push price down.
        Returns the adjusted price to feed back into the GBM simulator.
        """
        direction = Decimal("1") if side == "buy" else Decimal("-1")
        adjustment = Decimal(str(impact_bps)) / Decimal("10000")
        return current_price * (Decimal("1") + direction * adjustment)
