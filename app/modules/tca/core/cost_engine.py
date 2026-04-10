"""TCA cost decomposition engine — pure computation, no I/O.

Breaks total execution cost into:
- Commission: explicit broker fees
- Spread: half the bid-ask spread at arrival
- Timing: price drift between decision and execution (arrival vs VWAP)
- Market impact: premium/discount vs VWAP (fill price vs VWAP)
- Opportunity: cost of unfilled portion
- Implementation shortfall: total cost = sum of all components
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class TCAInput:
    side: str
    quantity: Decimal
    filled_quantity: Decimal
    avg_fill_price: Decimal
    arrival_mid_price: Decimal
    arrival_spread: Decimal
    vwap_benchmark: Decimal | None
    commission_rate_bps: Decimal
    adv: int | None
    execution_start: datetime
    execution_end: datetime
    terminal_price: Decimal | None


@dataclass(frozen=True)
class TCAResult:
    total_cost_bps: Decimal
    commission_cost_bps: Decimal
    spread_cost_bps: Decimal
    market_impact_cost_bps: Decimal
    timing_cost_bps: Decimal
    opportunity_cost_bps: Decimal
    implementation_shortfall_bps: Decimal
    participation_rate: Decimal | None
    execution_duration_seconds: int
    total_cost_usd: Decimal


_BPS = Decimal("10000")
_ZERO = Decimal("0")
_QUANT = Decimal("0.0001")


class CostEngine:
    """Pure-function TCA cost decomposition."""

    @staticmethod
    def compute(inp: TCAInput) -> TCAResult:
        sign = Decimal("1") if inp.side == "buy" else Decimal("-1")
        arrival = inp.arrival_mid_price

        if arrival <= 0:
            return _zero_result(inp)

        # Commission
        commission = inp.commission_rate_bps

        # Spread cost: half the spread at arrival
        spread = (inp.arrival_spread / Decimal("2") / arrival * _BPS).quantize(_QUANT)

        # Timing cost: drift between decision and execution
        timing = _ZERO
        if inp.vwap_benchmark is not None:
            timing = (sign * (inp.vwap_benchmark - arrival) / arrival * _BPS).quantize(_QUANT)

        # Market impact: premium paid vs VWAP
        impact = _ZERO
        if inp.vwap_benchmark is not None:
            impact = (sign * (inp.avg_fill_price - inp.vwap_benchmark) / arrival * _BPS).quantize(
                _QUANT
            )
        else:
            # No VWAP: compute as total slippage minus spread
            raw = (sign * (inp.avg_fill_price - arrival) / arrival * _BPS).quantize(_QUANT)
            impact = max(_ZERO, raw - spread)

        # Opportunity cost: unfilled portion
        opportunity = _ZERO
        if inp.filled_quantity < inp.quantity and inp.terminal_price is not None:
            unfilled_frac = Decimal("1") - inp.filled_quantity / inp.quantity
            price_move = (sign * (inp.terminal_price - arrival) / arrival * _BPS).quantize(_QUANT)
            opportunity = (unfilled_frac * price_move).quantize(_QUANT)

        # Implementation shortfall = sum of all components
        impl_shortfall = (commission + spread + timing + impact + opportunity).quantize(_QUANT)

        # Total cost in USD
        total_usd = (impl_shortfall / _BPS * arrival * inp.quantity).quantize(Decimal("0.01"))

        # Participation rate
        participation: Decimal | None = None
        if inp.adv and inp.adv > 0:
            participation = (inp.filled_quantity / Decimal(str(inp.adv))).quantize(
                Decimal("0.000001")
            )

        # Duration
        duration = max(0, int((inp.execution_end - inp.execution_start).total_seconds()))

        return TCAResult(
            total_cost_bps=impl_shortfall,
            commission_cost_bps=commission,
            spread_cost_bps=spread,
            market_impact_cost_bps=impact,
            timing_cost_bps=timing,
            opportunity_cost_bps=opportunity,
            implementation_shortfall_bps=impl_shortfall,
            participation_rate=participation,
            execution_duration_seconds=duration,
            total_cost_usd=total_usd,
        )


def _zero_result(inp: TCAInput) -> TCAResult:
    duration = max(0, int((inp.execution_end - inp.execution_start).total_seconds()))
    return TCAResult(
        total_cost_bps=_ZERO,
        commission_cost_bps=_ZERO,
        spread_cost_bps=_ZERO,
        market_impact_cost_bps=_ZERO,
        timing_cost_bps=_ZERO,
        opportunity_cost_bps=_ZERO,
        implementation_shortfall_bps=_ZERO,
        participation_rate=None,
        execution_duration_seconds=duration,
        total_cost_usd=_ZERO,
    )
