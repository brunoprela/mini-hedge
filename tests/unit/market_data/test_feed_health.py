"""Unit tests for FeedHealthMonitor — staleness detection across feeds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.market_data.core.feed_health import FeedHealthMonitor


@pytest.fixture
def monitor() -> FeedHealthMonitor:
    return FeedHealthMonitor(staleness_threshold=timedelta(minutes=5))


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 4, 12, 14, 0, 0, tzinfo=UTC)


class TestRecordUpdate:
    def test_tracks_new_feed(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now)
        assert monitor.tracked_count == 1

    def test_tracks_multiple_instruments(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now)
        monitor.record_update("MSFT", "bloomberg", now)
        assert monitor.tracked_count == 2

    def test_same_instrument_different_source_tracked_separately(
        self, monitor: FeedHealthMonitor, now: datetime
    ) -> None:
        monitor.record_update("AAPL", "bloomberg", now)
        monitor.record_update("AAPL", "reuters", now)
        assert monitor.tracked_count == 2

    def test_update_replaces_previous(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now)
        monitor.record_update("AAPL", "bloomberg", now + timedelta(seconds=30))
        assert monitor.tracked_count == 1


class TestHealthCheck:
    def test_fresh_feed_is_healthy(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now)
        report = monitor.check_health(now + timedelta(seconds=30))
        assert report.all_healthy
        assert report.total_feeds == 1
        assert report.stale_feeds == 0

    def test_stale_feed_detected(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now)
        report = monitor.check_health(now + timedelta(minutes=10))
        assert not report.all_healthy
        assert report.stale_feeds == 1
        assert "AAPL" in report.stale_instruments

    def test_mixed_health(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now - timedelta(minutes=10))
        monitor.record_update("MSFT", "bloomberg", now)
        report = monitor.check_health(now)
        assert report.total_feeds == 2
        assert report.stale_feeds == 1
        assert report.healthy_feeds == 1

    def test_empty_monitor_all_healthy(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        report = monitor.check_health(now)
        assert report.all_healthy
        assert report.total_feeds == 0


class TestStaleFeedsList:
    def test_get_stale_feeds_filters(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now - timedelta(minutes=10))
        monitor.record_update("MSFT", "bloomberg", now)
        stale = monitor.get_stale_feeds(now)
        assert len(stale) == 1
        assert stale[0].instrument_id == "AAPL"

    def test_age_seconds_calculated(self, monitor: FeedHealthMonitor, now: datetime) -> None:
        monitor.record_update("AAPL", "bloomberg", now - timedelta(minutes=3))
        report = monitor.check_health(now)
        status = report.statuses[0]
        assert abs(status.age_seconds - 180.0) < 0.1
