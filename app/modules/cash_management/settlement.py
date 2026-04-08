"""Settlement convention logic — calculates settlement dates.

Handles T+N settlement cycles per country, skipping weekends and
(optionally) market holidays when a :class:`HolidayCalendar` is provided.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from app.modules.cash_management.interface import (
    DEFAULT_SETTLEMENT_DAYS,
    SETTLEMENT_CONVENTIONS,
)

if TYPE_CHECKING:
    from app.modules.cash_management.holiday_calendar import HolidayCalendar


def get_settlement_days(country: str) -> int:
    """Return the T+N settlement cycle for a country."""
    return SETTLEMENT_CONVENTIONS.get(country, DEFAULT_SETTLEMENT_DAYS)


def calculate_settlement_date(
    trade_date: date,
    country: str,
    *,
    calendar: HolidayCalendar | None = None,
) -> date:
    """Calculate the settlement date given a trade date and country.

    When *calendar* is supplied, holidays for *country* are skipped in
    addition to weekends.  Otherwise only weekends are skipped (backward
    compatible behaviour).
    """
    n = get_settlement_days(country)
    return _add_business_days(trade_date, n, calendar=calendar, country=country)


def snap_to_business_day(
    d: date,
    *,
    calendar: HolidayCalendar | None = None,
    country: str | None = None,
) -> date:
    """If *d* falls on a non-business day, advance to the next business day."""
    if calendar is not None and country is not None:
        return calendar.next_business_day(d, country)
    # Weekends-only fallback
    wd = d.weekday()
    if wd == 5:  # Saturday
        return d + timedelta(days=2)
    if wd == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def is_business_day(
    d: date,
    *,
    calendar: HolidayCalendar | None = None,
    country: str | None = None,
) -> bool:
    """Return True if *d* is a business day.

    When *calendar* and *country* are provided, holidays are also
    checked.  Otherwise only weekends are considered.
    """
    if calendar is not None and country is not None:
        return calendar.is_business_day(d, country)
    return d.weekday() < 5


def _add_business_days(
    start: date,
    days: int,
    *,
    calendar: HolidayCalendar | None = None,
    country: str | None = None,
) -> date:
    """Add N business days to a date, skipping weekends (and holidays)."""
    if calendar is not None and country is not None:
        return calendar.add_business_days(start, days, country)

    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        # Monday=0, Sunday=6 — skip Saturday(5) and Sunday(6)
        if current.weekday() < 5:
            added += 1
    return current
