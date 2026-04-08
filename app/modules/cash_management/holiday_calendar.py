"""Market holiday calendar for settlement date calculations.

Provides fixed holiday schedules per country (US, GB, JP, DE) so that
settlement date logic can skip both weekends and market holidays.
"""

from __future__ import annotations

from datetime import date, timedelta


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the *n*-th occurrence of *weekday* (0=Mon) in *month*."""
    first = date(year, month, 1)
    # Days until first occurrence of *weekday*
    offset = (weekday - first.weekday()) % 7
    d = first + timedelta(days=offset)
    d += timedelta(weeks=n - 1)
    return d


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of *weekday* in *month*."""
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=offset)


def _easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_val = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l_val) // 451
    month, day = divmod(h + l_val - 7 * m + 114, 31)
    return date(year, month, day + 1)


# ------------------------------------------------------------------
# Per-country holiday builders
# ------------------------------------------------------------------


def _us_holidays(year: int) -> set[date]:
    """US federal / market holidays."""
    holidays: set[date] = set()

    # New Year's Day
    holidays.add(date(year, 1, 1))
    # MLK Day — 3rd Monday in January
    holidays.add(_nth_weekday(year, 1, 0, 3))
    # Presidents' Day — 3rd Monday in February
    holidays.add(_nth_weekday(year, 2, 0, 3))
    # Memorial Day — last Monday in May
    holidays.add(_last_weekday(year, 5, 0))
    # Independence Day
    holidays.add(date(year, 7, 4))
    # Labor Day — 1st Monday in September
    holidays.add(_nth_weekday(year, 9, 0, 1))
    # Thanksgiving — 4th Thursday in November
    holidays.add(_nth_weekday(year, 11, 3, 4))
    # Christmas Day
    holidays.add(date(year, 12, 25))

    return holidays


def _gb_holidays(year: int) -> set[date]:
    """UK bank holidays (England & Wales)."""
    holidays: set[date] = set()
    easter_sun = _easter(year)

    holidays.add(date(year, 1, 1))  # New Year's Day
    holidays.add(easter_sun - timedelta(days=2))  # Good Friday
    holidays.add(easter_sun + timedelta(days=1))  # Easter Monday
    # Early May bank holiday — 1st Monday in May
    holidays.add(_nth_weekday(year, 5, 0, 1))
    # Spring bank holiday — last Monday in May
    holidays.add(_last_weekday(year, 5, 0))
    # Summer bank holiday — last Monday in August
    holidays.add(_last_weekday(year, 8, 0))
    holidays.add(date(year, 12, 25))  # Christmas Day
    holidays.add(date(year, 12, 26))  # Boxing Day

    return holidays


def _jp_holidays(year: int) -> set[date]:
    """Japanese national holidays."""
    holidays: set[date] = set()

    # New Year's holidays
    holidays.add(date(year, 1, 1))
    holidays.add(date(year, 1, 2))
    holidays.add(date(year, 1, 3))
    # Coming of Age Day — 2nd Monday in January
    holidays.add(_nth_weekday(year, 1, 0, 2))
    # National Foundation Day
    holidays.add(date(year, 2, 11))
    # Vernal Equinox (approx Mar 20)
    holidays.add(date(year, 3, 20))
    # Showa Day
    holidays.add(date(year, 4, 29))
    # Constitution Memorial Day
    holidays.add(date(year, 5, 3))
    # Greenery Day
    holidays.add(date(year, 5, 4))
    # Children's Day
    holidays.add(date(year, 5, 5))
    # Marine Day — 3rd Monday in July
    holidays.add(_nth_weekday(year, 7, 0, 3))
    # Mountain Day
    holidays.add(date(year, 8, 11))
    # Respect for the Aged Day — 3rd Monday in September
    holidays.add(_nth_weekday(year, 9, 0, 3))
    # Autumnal Equinox (approx Sep 23)
    holidays.add(date(year, 9, 23))
    # Sports Day — 2nd Monday in October
    holidays.add(_nth_weekday(year, 10, 0, 2))
    # Culture Day
    holidays.add(date(year, 11, 3))
    # Labor Thanksgiving Day
    holidays.add(date(year, 11, 23))

    return holidays


def _de_holidays(year: int) -> set[date]:
    """German national holidays."""
    holidays: set[date] = set()
    easter_sun = _easter(year)

    holidays.add(date(year, 1, 1))  # New Year's Day
    holidays.add(easter_sun - timedelta(days=2))  # Good Friday
    holidays.add(easter_sun + timedelta(days=1))  # Easter Monday
    holidays.add(date(year, 5, 1))  # Labour Day
    holidays.add(easter_sun + timedelta(days=39))  # Ascension Day
    holidays.add(easter_sun + timedelta(days=50))  # Whit Monday
    holidays.add(date(year, 10, 3))  # German Unity Day
    holidays.add(date(year, 12, 25))  # Christmas Day
    holidays.add(date(year, 12, 26))  # Second Day of Christmas

    return holidays


_BUILDERS: dict[str, type[None] | None] = None  # type: ignore[assignment]

_COUNTRY_BUILDERS = {
    "US": _us_holidays,
    "GB": _gb_holidays,
    "JP": _jp_holidays,
    "DE": _de_holidays,
}

# Year range to pre-build
_YEAR_LO = 2024
_YEAR_HI = 2030


class HolidayCalendar:
    """Market holiday calendar for settlement date calculations."""

    _holidays: dict[str, set[date]]

    def __init__(self) -> None:
        self._holidays = self._build_calendar()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_holiday(self, d: date, country: str) -> bool:
        """Return True if *d* is a market holiday in *country*."""
        holidays = self._holidays.get(country.upper())
        if holidays is None:
            return False
        return d in holidays

    def is_business_day(self, d: date, country: str) -> bool:
        """True if *d* is not a weekend and not a holiday."""
        if d.weekday() >= 5:
            return False
        return not self.is_holiday(d, country)

    def next_business_day(self, d: date, country: str) -> date:
        """Return *d* if it is a business day, otherwise advance to the next one."""
        while not self.is_business_day(d, country):
            d += timedelta(days=1)
        return d

    def add_business_days(self, start: date, days: int, country: str) -> date:
        """Add *days* business days to *start*, skipping weekends and holidays."""
        current = start
        added = 0
        while added < days:
            current += timedelta(days=1)
            if self.is_business_day(current, country):
                added += 1
        return current

    def get_holidays(self, country: str, year: int) -> list[date]:
        """Return sorted list of holidays for *country* in *year*."""
        country = country.upper()
        builder = _COUNTRY_BUILDERS.get(country)
        if builder is None:
            return []
        return sorted(d for d in builder(year))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_calendar() -> dict[str, set[date]]:
        result: dict[str, set[date]] = {}
        for code, builder in _COUNTRY_BUILDERS.items():
            combined: set[date] = set()
            for year in range(_YEAR_LO, _YEAR_HI + 1):
                combined |= builder(year)
            result[code] = combined
        return result
