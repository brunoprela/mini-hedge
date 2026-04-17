"""FX forward pricing and hedging calculations — pure functions, no I/O.

Implements:
- Forward rate via covered interest rate parity
- Mark-to-market valuation of open forwards
- Carry P&L decomposition (spot vs. forward points)
- Hedge recommendations from currency exposure
- Roll cost estimation
- Expiry detection
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

ZERO = Decimal(0)
ONE = Decimal(1)
BPS = Decimal("0.0001")
DAYS_IN_YEAR = Decimal(360)


@dataclass(frozen=True)
class ForwardRate:
    """Result of a forward rate calculation."""

    spot: Decimal
    forward: Decimal
    forward_points: Decimal  # forward - spot
    domestic_rate: Decimal
    foreign_rate: Decimal
    tenor_days: int


@dataclass(frozen=True)
class ForwardMTM:
    """Mark-to-market of an existing forward contract."""

    contract_forward: Decimal
    current_forward: Decimal
    notional: Decimal
    mtm_value: Decimal  # positive = in the money
    currency: str


@dataclass(frozen=True)
class CarryPnL:
    """P&L decomposition of a forward position."""

    spot_pnl: Decimal  # from spot rate movement
    carry_pnl: Decimal  # from interest rate differential (forward points)
    total_pnl: Decimal


@dataclass(frozen=True)
class HedgeRecommendation:
    """Suggested hedge for a currency exposure."""

    currency_pair: str
    base_currency: str
    quote_currency: str
    notional: Decimal  # in base currency
    direction: str  # "buy" or "sell"
    hedge_ratio: Decimal
    tenor_days: int
    estimated_forward: Decimal
    estimated_cost_bps: Decimal


@dataclass(frozen=True)
class RollCost:
    """Estimated cost of rolling a forward to a new maturity."""

    old_forward: Decimal
    new_forward: Decimal
    close_mtm: Decimal  # P&L from closing existing contract
    cost_bps: Decimal  # net cost in basis points


def calculate_forward_rate(
    spot: Decimal,
    domestic_rate: Decimal,
    foreign_rate: Decimal,
    tenor_days: int,
) -> ForwardRate:
    """Calculate forward rate using covered interest rate parity.

    F = S * (1 + r_d * T) / (1 + r_f * T)

    Where:
    - S = spot rate (domestic per foreign, e.g. 1.25 USD/EUR)
    - r_d = domestic (quote) interest rate (annualized)
    - r_f = foreign (base) interest rate (annualized)
    - T = time fraction (tenor_days / 360)
    """
    t = Decimal(tenor_days) / DAYS_IN_YEAR
    forward = spot * (ONE + domestic_rate * t) / (ONE + foreign_rate * t)
    forward = forward.quantize(Decimal("0.000001"))
    return ForwardRate(
        spot=spot,
        forward=forward,
        forward_points=forward - spot,
        domestic_rate=domestic_rate,
        foreign_rate=foreign_rate,
        tenor_days=tenor_days,
    )


def mark_to_market_forward(
    contract_rate: Decimal,
    contract_notional: Decimal,
    contract_direction: str,
    current_spot: Decimal,
    domestic_rate: Decimal,
    foreign_rate: Decimal,
    remaining_days: int,
    quote_currency: str,
) -> ForwardMTM:
    """Mark-to-market an open forward contract.

    Computes the current forward rate for the remaining tenor, then
    calculates P&L as the difference between contract and current forward
    applied to the notional.
    """
    current_fwd = calculate_forward_rate(
        current_spot,
        domestic_rate,
        foreign_rate,
        remaining_days,
    )
    sign = ONE if contract_direction == "buy" else -ONE
    mtm = sign * contract_notional * (current_fwd.forward - contract_rate)
    return ForwardMTM(
        contract_forward=contract_rate,
        current_forward=current_fwd.forward,
        notional=contract_notional,
        mtm_value=mtm.quantize(Decimal("0.01")),
        currency=quote_currency,
    )


def calculate_carry_pnl(
    entry_spot: Decimal,
    current_spot: Decimal,
    contract_rate: Decimal,
    current_forward: Decimal,
    notional: Decimal,
    direction: str,
) -> CarryPnL:
    """Decompose forward P&L into spot movement and carry components.

    - Spot P&L: notional * (current_spot - entry_spot) * sign
    - Carry P&L: total - spot (the interest rate differential component)
    """
    sign = ONE if direction == "buy" else -ONE
    spot_pnl = sign * notional * (current_spot - entry_spot)
    total_pnl = sign * notional * (current_forward - contract_rate)
    carry = total_pnl - spot_pnl
    return CarryPnL(
        spot_pnl=spot_pnl.quantize(Decimal("0.01")),
        carry_pnl=carry.quantize(Decimal("0.01")),
        total_pnl=total_pnl.quantize(Decimal("0.01")),
    )


def recommend_hedges(
    currency_exposures: dict[str, Decimal],
    base_currency: str,
    spots: dict[str, Decimal],
    domestic_rate: Decimal,
    foreign_rates: dict[str, Decimal],
    hedge_ratio: Decimal = Decimal("1.0"),
    tenor_days: int = 30,
) -> list[HedgeRecommendation]:
    """Generate hedge recommendations from currency exposures.

    Args:
        currency_exposures: {currency: net_exposure_in_that_currency}
        base_currency: Fund's base currency (e.g. "USD")
        spots: {currency: spot_rate vs base}
        domestic_rate: Base currency interest rate
        foreign_rates: {currency: interest_rate}
        hedge_ratio: Target hedge ratio (1.0 = fully hedged)
        tenor_days: Default forward tenor
    """
    recommendations: list[HedgeRecommendation] = []
    for ccy, exposure in currency_exposures.items():
        if ccy == base_currency or exposure == ZERO:
            continue
        spot = spots.get(ccy)
        if spot is None or spot <= ZERO:
            continue
        foreign_rate = foreign_rates.get(ccy, ZERO)
        fwd = calculate_forward_rate(spot, domestic_rate, foreign_rate, tenor_days)

        hedge_notional = abs(exposure) * hedge_ratio
        # If we have positive exposure in foreign ccy, sell forward to hedge
        direction = "sell" if exposure > ZERO else "buy"
        cost_bps = abs(fwd.forward_points / spot) / BPS

        recommendations.append(
            HedgeRecommendation(
                currency_pair=f"{base_currency}/{ccy}",
                base_currency=base_currency,
                quote_currency=ccy,
                notional=hedge_notional.quantize(Decimal("0.01")),
                direction=direction,
                hedge_ratio=hedge_ratio,
                tenor_days=tenor_days,
                estimated_forward=fwd.forward,
                estimated_cost_bps=cost_bps.quantize(Decimal("0.01")),
            )
        )
    return recommendations


def identify_expiring_forwards(
    maturities: list[tuple[str, date]],
    as_of: date,
    days_ahead: int = 5,
) -> list[tuple[str, date, int]]:
    """Identify forwards expiring within a window.

    Args:
        maturities: list of (forward_id, maturity_date)
        as_of: current date
        days_ahead: look-ahead window

    Returns:
        list of (forward_id, maturity_date, days_remaining)
    """
    cutoff = as_of + timedelta(days=days_ahead)
    expiring: list[tuple[str, date, int]] = []
    for fwd_id, maturity in maturities:
        if maturity <= cutoff:
            days_remaining = (maturity - as_of).days
            expiring.append((fwd_id, maturity, max(days_remaining, 0)))
    return sorted(expiring, key=lambda x: x[2])


def calculate_roll_cost(
    contract_rate: Decimal,
    contract_notional: Decimal,
    direction: str,
    current_spot: Decimal,
    domestic_rate: Decimal,
    foreign_rate: Decimal,
    remaining_days: int,
    new_tenor_days: int,
) -> RollCost:
    """Estimate the cost of rolling a forward to a new maturity.

    Roll = close existing forward at current forward + open new forward.
    """
    # Close leg: MTM of existing contract
    close_fwd = calculate_forward_rate(
        current_spot,
        domestic_rate,
        foreign_rate,
        remaining_days,
    )
    sign = ONE if direction == "buy" else -ONE
    close_mtm = sign * contract_notional * (close_fwd.forward - contract_rate)

    # New leg: forward for new tenor
    new_fwd = calculate_forward_rate(
        current_spot,
        domestic_rate,
        foreign_rate,
        new_tenor_days,
    )

    # Cost in bps: the forward points difference relative to spot
    if current_spot <= ZERO:
        cost_bps = ZERO
    else:
        cost_bps = abs(new_fwd.forward_points / current_spot) / BPS

    return RollCost(
        old_forward=close_fwd.forward,
        new_forward=new_fwd.forward,
        close_mtm=close_mtm.quantize(Decimal("0.01")),
        cost_bps=cost_bps.quantize(Decimal("0.01")),
    )
