"""Exchange trading hours — UTC-based schedules for order acceptance.

Each exchange has defined trading hours. Orders submitted outside these
windows are rejected with a clear reason. The ambient flow generator
also uses these to only produce volume during market hours.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta


@dataclass(frozen=True)
class ExchangeSchedule:
    """Trading schedule for a single exchange."""

    exchange_id: str
    name: str
    open_utc: time    # Market open in UTC
    close_utc: time   # Market close in UTC
    timezone: str     # Display timezone (informational)
    trading_days: tuple[int, ...] = (0, 1, 2, 3, 4)  # Mon-Fri

    def is_open(self, now: datetime | None = None) -> bool:
        """Check if the exchange is currently open for trading."""
        if now is None:
            now = datetime.now(UTC)
        # Check day of week (0=Monday)
        if now.weekday() not in self.trading_days:
            return False
        current_time = now.time()
        return self.open_utc <= current_time < self.close_utc

    def minutes_since_open(self, now: datetime | None = None) -> int:
        """Minutes elapsed since market open. Returns -1 if market is closed."""
        if not self.is_open(now):
            return -1
        if now is None:
            now = datetime.now(UTC)
        open_dt = datetime.combine(now.date(), self.open_utc, tzinfo=UTC)
        return int((now - open_dt).total_seconds() / 60)

    @property
    def trading_minutes(self) -> int:
        """Total minutes in a trading session."""
        open_dt = datetime.combine(datetime.now(UTC).date(), self.open_utc, tzinfo=UTC)
        close_dt = datetime.combine(datetime.now(UTC).date(), self.close_utc, tzinfo=UTC)
        return int((close_dt - open_dt).total_seconds() / 60)

    def next_open(self, now: datetime | None = None) -> datetime:
        """Return the next market open datetime."""
        if now is None:
            now = datetime.now(UTC)
        candidate = datetime.combine(now.date(), self.open_utc, tzinfo=UTC)
        if candidate <= now:
            candidate += timedelta(days=1)
        while candidate.weekday() not in self.trading_days:
            candidate += timedelta(days=1)
        return candidate


# ── Exchange schedules (UTC times) ────────────────────────────────

EXCHANGE_SCHEDULES: dict[str, ExchangeSchedule] = {
    # US exchanges: 09:30-16:00 ET = 14:30-21:00 UTC
    "NYSE": ExchangeSchedule(
        exchange_id="NYSE",
        name="New York Stock Exchange",
        open_utc=time(14, 30),
        close_utc=time(21, 0),
        timezone="America/New_York",
    ),
    "NASDAQ": ExchangeSchedule(
        exchange_id="NASDAQ",
        name="NASDAQ",
        open_utc=time(14, 30),
        close_utc=time(21, 0),
        timezone="America/New_York",
    ),
    # London: 08:00-16:30 GMT = 08:00-16:30 UTC
    "LSE": ExchangeSchedule(
        exchange_id="LSE",
        name="London Stock Exchange",
        open_utc=time(8, 0),
        close_utc=time(16, 30),
        timezone="Europe/London",
    ),
    # Germany: 09:00-17:30 CET = 08:00-16:30 UTC
    "XETRA": ExchangeSchedule(
        exchange_id="XETRA",
        name="Deutsche Börse (Xetra)",
        open_utc=time(8, 0),
        close_utc=time(16, 30),
        timezone="Europe/Berlin",
    ),
    # France/Netherlands: 09:00-17:30 CET = 08:00-16:30 UTC
    "EURONEXT": ExchangeSchedule(
        exchange_id="EURONEXT",
        name="Euronext",
        open_utc=time(8, 0),
        close_utc=time(16, 30),
        timezone="Europe/Paris",
    ),
    # Denmark: 09:00-17:00 CET = 08:00-16:00 UTC
    "CPH": ExchangeSchedule(
        exchange_id="CPH",
        name="Nasdaq Copenhagen",
        open_utc=time(8, 0),
        close_utc=time(16, 0),
        timezone="Europe/Copenhagen",
    ),
    # Japan: 09:00-15:00 JST = 00:00-06:00 UTC
    "TSE": ExchangeSchedule(
        exchange_id="TSE",
        name="Tokyo Stock Exchange",
        open_utc=time(0, 0),
        close_utc=time(6, 0),
        timezone="Asia/Tokyo",
    ),
    # Switzerland: 09:00-17:30 CET = 08:00-16:30 UTC
    "SIX": ExchangeSchedule(
        exchange_id="SIX",
        name="SIX Swiss Exchange",
        open_utc=time(8, 0),
        close_utc=time(16, 30),
        timezone="Europe/Zurich",
    ),
    # South Korea: 09:00-15:30 KST = 00:00-06:30 UTC
    "KRX": ExchangeSchedule(
        exchange_id="KRX",
        name="Korea Exchange",
        open_utc=time(0, 0),
        close_utc=time(6, 30),
        timezone="Asia/Seoul",
    ),
    # Taiwan: 09:00-13:30 CST = 01:00-05:30 UTC
    "TWSE": ExchangeSchedule(
        exchange_id="TWSE",
        name="Taiwan Stock Exchange",
        open_utc=time(1, 0),
        close_utc=time(5, 30),
        timezone="Asia/Taipei",
    ),
    # Hong Kong: 09:30-16:00 HKT = 01:30-08:00 UTC
    "HKEX": ExchangeSchedule(
        exchange_id="HKEX",
        name="Hong Kong Exchange",
        open_utc=time(1, 30),
        close_utc=time(8, 0),
        timezone="Asia/Hong_Kong",
    ),
    # Australia: 10:00-16:00 AEST = 00:00-06:00 UTC
    "ASX": ExchangeSchedule(
        exchange_id="ASX",
        name="Australian Securities Exchange",
        open_utc=time(0, 0),
        close_utc=time(6, 0),
        timezone="Australia/Sydney",
    ),
    # Canada: 09:30-16:00 ET = 14:30-21:00 UTC
    "TSX": ExchangeSchedule(
        exchange_id="TSX",
        name="Toronto Stock Exchange",
        open_utc=time(14, 30),
        close_utc=time(21, 0),
        timezone="America/Toronto",
    ),
    # Brazil: 10:00-17:00 BRT = 13:00-20:00 UTC
    "B3": ExchangeSchedule(
        exchange_id="B3",
        name="B3 (Brasil Bolsa Balcão)",
        open_utc=time(13, 0),
        close_utc=time(20, 0),
        timezone="America/Sao_Paulo",
    ),
}


def get_schedule(exchange: str) -> ExchangeSchedule | None:
    """Get the trading schedule for an exchange."""
    return EXCHANGE_SCHEDULES.get(exchange)


def is_market_open(exchange: str, now: datetime | None = None) -> bool:
    """Check if a specific exchange is currently open."""
    schedule = EXCHANGE_SCHEDULES.get(exchange)
    if schedule is None:
        return True  # Unknown exchange — default to open (fail-open)
    return schedule.is_open(now)


def any_market_open(now: datetime | None = None) -> bool:
    """Check if any exchange is currently open."""
    return any(s.is_open(now) for s in EXCHANGE_SCHEDULES.values())
