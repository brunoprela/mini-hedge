"""Feed health monitor — detects stale market data feeds.

Tracks the last update timestamp per instrument and per source, and
reports which feeds have gone stale beyond a configurable threshold.
Designed to be called periodically (e.g. every 30s from a background task)
or on-demand from an API route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class FeedStatus:
    """Health status of a single instrument feed."""

    instrument_id: str
    source: str
    last_update: datetime
    age_seconds: float
    is_stale: bool


@dataclass(frozen=True)
class FeedHealthReport:
    """Aggregate health report across all tracked feeds."""

    checked_at: datetime
    total_feeds: int
    stale_feeds: int
    healthy_feeds: int
    statuses: list[FeedStatus]

    @property
    def all_healthy(self) -> bool:
        return self.stale_feeds == 0

    @property
    def stale_instruments(self) -> list[str]:
        return [s.instrument_id for s in self.statuses if s.is_stale]


@dataclass
class _FeedEntry:
    """Internal tracking entry for a single feed."""

    instrument_id: str
    source: str
    last_update: datetime
    last_price: Decimal | None = None


class FeedHealthMonitor:
    """Monitors market data feed freshness.

    Args:
        staleness_threshold: duration after which a feed is considered stale
    """

    def __init__(
        self,
        *,
        staleness_threshold: timedelta = timedelta(minutes=5),
    ) -> None:
        self.staleness_threshold = staleness_threshold
        self._feeds: dict[str, _FeedEntry] = {}

    def record_update(
        self,
        instrument_id: str,
        source: str,
        timestamp: datetime,
        price: Decimal | None = None,
    ) -> None:
        """Record that a price update was received for an instrument."""
        key = f"{instrument_id}:{source}"
        self._feeds[key] = _FeedEntry(
            instrument_id=instrument_id,
            source=source,
            last_update=timestamp,
            last_price=price,
        )

    def check_health(self, now: datetime | None = None) -> FeedHealthReport:
        """Check all tracked feeds and return a health report."""
        now = now or datetime.now(UTC)
        statuses: list[FeedStatus] = []

        for entry in self._feeds.values():
            age = now - entry.last_update
            statuses.append(
                FeedStatus(
                    instrument_id=entry.instrument_id,
                    source=entry.source,
                    last_update=entry.last_update,
                    age_seconds=age.total_seconds(),
                    is_stale=age > self.staleness_threshold,
                )
            )

        stale = sum(1 for s in statuses if s.is_stale)
        return FeedHealthReport(
            checked_at=now,
            total_feeds=len(statuses),
            stale_feeds=stale,
            healthy_feeds=len(statuses) - stale,
            statuses=statuses,
        )

    def get_stale_feeds(self, now: datetime | None = None) -> list[FeedStatus]:
        """Convenience: return only the stale feeds."""
        report = self.check_health(now)
        return [s for s in report.statuses if s.is_stale]

    @property
    def tracked_count(self) -> int:
        return len(self._feeds)
