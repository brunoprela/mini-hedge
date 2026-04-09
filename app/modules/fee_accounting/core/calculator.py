"""Fee calculation — pure functions, no I/O."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def calculate_daily_management_fee(nav: Decimal, annual_bps: int) -> Decimal:
    """Calculate one day's management fee accrual.

    Formula: nav * bps / 10_000 / 365
    """
    return (nav * Decimal(annual_bps) / Decimal(10_000) / Decimal(365)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def calculate_performance_fee(
    current_nav: Decimal,
    hwm_nav: Decimal,
    pct: Decimal,
    hurdle_annual: Decimal,
    days: int,
) -> Decimal:
    """Calculate performance fee on gains above HWM adjusted for hurdle.

    The hurdle is pro-rated for the number of days elapsed since the last
    crystallization.  Only gains above ``hwm_nav * (1 + prorated_hurdle)``
    are subject to the performance fee.

    Returns zero when current NAV is at or below the hurdle-adjusted HWM.
    """
    if current_nav <= hwm_nav:
        return Decimal(0)

    prorated_hurdle = hurdle_annual / Decimal(100) * Decimal(days) / Decimal(365)
    hurdle_adjusted_hwm = hwm_nav * (Decimal(1) + prorated_hurdle)

    gain = current_nav - hurdle_adjusted_hwm
    if gain <= 0:
        return Decimal(0)

    fee = gain * pct / Decimal(100)
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def should_crystallize(frequency: str, current_date: date) -> bool:
    """Check whether *current_date* is a crystallization boundary.

    Supported frequencies:
    - ``"quarterly"`` — last day of March, June, September, December
    - ``"annual"`` — December 31
    """
    if frequency == "quarterly":
        # Quarter-end: last day of months 3, 6, 9, 12
        if current_date.month not in (3, 6, 9, 12):
            return False
        # Check if this is the last day of the month
        next_day = current_date.toordinal() + 1
        from datetime import date as _date

        next_date = _date.fromordinal(next_day)
        return next_date.month != current_date.month
    elif frequency == "annual":
        return current_date.month == 12 and current_date.day == 31
    return False
