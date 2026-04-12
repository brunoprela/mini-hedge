"""Unit tests for market data feed status event publishing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.market_data.core.feed_health import FeedHealthMonitor
from app.modules.market_data.core.ingestion import MarketDataIngestionService
from app.shared.audit.events import AuditEventType


class TestMarketDataStatusEventType:
    def test_event_type_value(self) -> None:
        assert AuditEventType.MARKET_DATA_STATUS == "market_data.status"


class TestFeedStatusPublishing:
    def _make_service(self, *, event_bus=None, feed_monitor=None):
        return MarketDataIngestionService(
            market_data_service=MagicMock(),
            event_bus=event_bus,
            feed_monitor=feed_monitor,
        )

    @pytest.mark.asyncio
    async def test_publish_feed_status_skips_without_bus(self) -> None:
        service = self._make_service(event_bus=None)
        # Should not raise
        await service.publish_feed_status()

    @pytest.mark.asyncio
    async def test_publish_feed_status_calls_event_bus(self) -> None:
        mock_bus = AsyncMock()
        monitor = FeedHealthMonitor()
        # Record an update so we have a feed
        monitor.record_update(
            instrument_id="AAPL",
            source="bloomberg",
            timestamp=datetime.now(UTC),
            price=150.0,
        )
        service = self._make_service(event_bus=mock_bus, feed_monitor=monitor)
        await service.publish_feed_status()

        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        assert "market-data.status" in topic
        event = mock_bus.publish.call_args[0][1]
        assert event.event_type == AuditEventType.MARKET_DATA_STATUS
        assert event.data["total_feeds"] == 1
        assert event.data["healthy_feeds"] == 1
        assert event.data["stale_feeds"] == 0
        assert event.data["all_healthy"] is True

    @pytest.mark.asyncio
    async def test_publish_feed_status_reports_stale_feeds(self) -> None:
        mock_bus = AsyncMock()
        monitor = FeedHealthMonitor(staleness_threshold=timedelta(seconds=1))
        # Record an old update that will be stale
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        monitor.record_update(
            instrument_id="AAPL",
            source="bloomberg",
            timestamp=old_time,
            price=150.0,
        )
        service = self._make_service(event_bus=mock_bus, feed_monitor=monitor)
        await service.publish_feed_status()

        event = mock_bus.publish.call_args[0][1]
        assert event.data["stale_feeds"] == 1
        assert event.data["all_healthy"] is False
        assert "AAPL" in event.data["stale_instruments"]

    @pytest.mark.asyncio
    async def test_feed_monitor_property(self) -> None:
        monitor = FeedHealthMonitor()
        service = self._make_service(feed_monitor=monitor)
        assert service.feed_monitor is monitor
