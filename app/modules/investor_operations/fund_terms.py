"""Pure functions for fund terms calculations.

No I/O, no side effects — only date arithmetic and threshold checks.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from app.modules.investor_operations.interface import RedemptionFrequency


def compute_next_dealing_date(
    frequency: RedemptionFrequency,
    dealing_day: int,
    from_date: date,
) -> date:
    """Return the next dealing date on or after *from_date*.

    *dealing_day* is the day-of-month for dealing.  ``-1`` means the last
    business day of the period.
    """
    if frequency == RedemptionFrequency.MONTHLY:
        candidates = _monthly_candidates(from_date, dealing_day, months=3)
    elif frequency == RedemptionFrequency.QUARTERLY:
        candidates = _quarterly_candidates(from_date, dealing_day)
    elif frequency == RedemptionFrequency.ANNUAL:
        candidates = _annual_candidates(from_date, dealing_day)
    else:
        msg = f"Unsupported frequency: {frequency}"
        raise ValueError(msg)

    for d in candidates:
        adj = _adjust_to_business_day(d)
        if adj >= from_date:
            return adj

    # Fallback — should never happen with enough candidates
    return _adjust_to_business_day(candidates[-1])


def check_lock_up(
    subscription_date: date,
    lock_up_months: int,
    request_date: date,
) -> bool:
    """Return True if the lock-up period has expired (redemption allowed)."""
    expiry = _add_months(subscription_date, lock_up_months)
    return request_date >= expiry


def compute_lock_up_expiry(subscription_date: date, lock_up_months: int) -> date:
    """Return the date when the lock-up period ends."""
    return _add_months(subscription_date, lock_up_months)


def compute_notice_deadline(notice_date: date, notice_period_days: int) -> date:
    """Return the earliest date a redemption can be processed after notice."""
    return notice_date + timedelta(days=notice_period_days)


def compute_payment_due_date(dealing_date: date, payment_days: int) -> date:
    """Return the date by which redemption proceeds must be paid."""
    return dealing_date + timedelta(days=payment_days)


def validate_minimum_amount(amount: Decimal, minimum: Decimal) -> bool:
    """Return True if *amount* meets or exceeds the minimum."""
    return amount >= minimum


# ---------------------------------------------------------------------------
#  Internal helpers
# ---------------------------------------------------------------------------


def _add_months(d: date, months: int) -> date:
    """Add *months* to a date, clamping to end-of-month if needed."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, max_day))


def _resolve_dealing_day(year: int, month: int, dealing_day: int) -> date:
    """Resolve dealing_day (possibly -1) to a concrete date."""
    max_day = calendar.monthrange(year, month)[1]
    if dealing_day == -1:
        return date(year, month, max_day)
    return date(year, month, min(dealing_day, max_day))


def _adjust_to_business_day(d: date) -> date:
    """Move weekends backward to the preceding Friday."""
    weekday = d.weekday()
    if weekday == 5:  # Saturday
        return d - timedelta(days=1)
    if weekday == 6:  # Sunday
        return d - timedelta(days=2)
    return d


def _monthly_candidates(from_date: date, dealing_day: int, months: int) -> list[date]:
    """Generate *months* dealing-date candidates starting from from_date's month."""
    results: list[date] = []
    year, month = from_date.year, from_date.month
    for _ in range(months):
        results.append(_resolve_dealing_day(year, month, dealing_day))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return results


def _quarterly_candidates(from_date: date, dealing_day: int) -> list[date]:
    """Generate quarterly dealing-date candidates (Mar, Jun, Sep, Dec boundaries)."""
    quarter_ends = [3, 6, 9, 12]
    results: list[date] = []
    year = from_date.year
    for _ in range(2):  # Two years of quarters
        for m in quarter_ends:
            results.append(_resolve_dealing_day(year, m, dealing_day))
        year += 1
    return results


def _annual_candidates(from_date: date, dealing_day: int) -> list[date]:
    """Generate annual dealing-date candidates (December)."""
    results: list[date] = []
    for year in range(from_date.year, from_date.year + 3):
        results.append(_resolve_dealing_day(year, 12, dealing_day))
    return results
