"""Settlement convention logic — calculates settlement dates.

Handles T+N settlement cycles per country, skipping weekends.
Business day calendars with actual holidays are deferred to Phase 4
(would require a holiday calendar service or library like `exchange_calendars`).
"""

from __future__ import annotations

from datetime import date, timedelta

from app.modules.cash_management.interface import (
    DEFAULT_SETTLEMENT_DAYS,
    SETTLEMENT_CONVENTIONS,
)


def get_settlement_days(country: str) -> int:
    """Return the T+N settlement cycle for a country."""
    return SETTLEMENT_CONVENTIONS.get(country, DEFAULT_SETTLEMENT_DAYS)


def calculate_settlement_date(trade_date: date, country: str) -> date:
    """Calculate the settlement date given a trade date and country.

    Adds T+N business days (skipping weekends, not holidays).
    """
    n = get_settlement_days(country)
    return _add_business_days(trade_date, n)


def _add_business_days(start: date, days: int) -> date:
    """Add N business days to a date, skipping weekends."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        # Monday=0, Sunday=6 — skip Saturday(5) and Sunday(6)
        if current.weekday() < 5:
            added += 1
    return current
