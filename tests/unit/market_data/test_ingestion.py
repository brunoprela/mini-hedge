"""Unit tests for MarketDataIngestionService — validate/dedup/store/publish pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.market_data.core.feed_health import FeedHealthMonitor
from app.modules.market_data.core.ingestion import MarketDataIngestionService
from app.modules.market_data.core.price_validator import PriceValidator
from app.modules.market_data.interfaces import PriceSnapshot
from app.shared.events import InProcessEventBus
from tests.factories import make_price


def _make_service(
    *,
    event_bus: InProcessEventBus | None = None,
    dedup_window: int = 1,
    max_spread_bps: Decimal = Decimal("500"),
) -> tuple[MarketDataIngestionService, AsyncMock]:
    """Build an ingestion service with a mocked MarketDataService."""
    md_service = AsyncMock()
    md_service.store_price = AsyncMock()
    md_service.update_latest = MagicMock()  # sync method, not async

    return (
        MarketDataIngestionService(
            market_data_service=md_service,
            validator=PriceValidator(max_spread_bps=max_spread_bps),
            feed_monitor=FeedHealthMonitor(),
            event_bus=event_bus,
            dedup_window_seconds=dedup_window,
        ),
        md_service,
    )


class TestIngestionHappyPath:
    @pytest.mark.asyncio
    async def test_valid_price_is_accepted(self) -> None:
        svc, md = _make_service()
        price = make_price(instrument_id="AAPL", mid=Decimal("150.00"))

        result = await svc.ingest(price)

        assert result.accepted
        assert result.reason == "ok"
        md.store_price.assert_awaited_once_with(price)
        md.update_latest.assert_called_once_with(price)

    @pytest.mark.asyncio
    async def test_feed_monitor_records_update(self) -> None:
        svc, _ = _make_service()
        price = make_price(instrument_id="MSFT", mid=Decimal("400.00"))

        await svc.ingest(price)

        assert svc.feed_monitor.tracked_count == 1
        report = svc.feed_monitor.check_health()
        assert report.total_feeds == 1
        assert report.all_healthy

    @pytest.mark.asyncio
    async def test_batch_ingest(self) -> None:
        svc, md = _make_service(dedup_window=0)
        prices = [
            make_price(instrument_id="AAPL", mid=Decimal("150.00")),
            make_price(instrument_id="MSFT", mid=Decimal("400.00")),
            make_price(instrument_id="GOOGL", mid=Decimal("180.00")),
        ]

        result = await svc.ingest_batch(prices)

        assert result.total == 3
        assert result.accepted == 3
        assert result.rejected == 0
        assert result.duplicates == 0
        assert md.store_price.await_count == 3


class TestIngestionValidation:
    @pytest.mark.asyncio
    async def test_negative_price_rejected(self) -> None:
        svc, md = _make_service()
        price = PriceSnapshot(
            instrument_id="BAD",
            bid=Decimal("-1.00"),
            ask=Decimal("1.00"),
            mid=Decimal("0.00"),
            timestamp=datetime.now(UTC),
            source="test",
        )

        result = await svc.ingest(price)

        assert not result.accepted
        assert result.reason == "validation_failed"
        assert result.validation_report is not None
        assert not result.validation_report.valid
        md.store_price.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wide_spread_rejected(self) -> None:
        svc, md = _make_service(max_spread_bps=Decimal("10"))
        # 10% spread = 1000 bps, far exceeds 10 bps limit
        price = PriceSnapshot(
            instrument_id="WIDE",
            bid=Decimal("95.00"),
            ask=Decimal("105.00"),
            mid=Decimal("100.00"),
            timestamp=datetime.now(UTC),
            source="test",
        )

        result = await svc.ingest(price)

        assert not result.accepted
        assert result.reason == "validation_failed"

    @pytest.mark.asyncio
    async def test_stale_price_rejected(self) -> None:
        svc, _ = _make_service()
        old_time = datetime.now(UTC) - timedelta(hours=1)
        price = make_price(instrument_id="STALE", timestamp=old_time)

        result = await svc.ingest(price)

        assert not result.accepted
        assert result.reason == "validation_failed"

    @pytest.mark.asyncio
    async def test_crossed_market_rejected(self) -> None:
        svc, _ = _make_service()
        price = PriceSnapshot(
            instrument_id="CROSS",
            bid=Decimal("105.00"),
            ask=Decimal("95.00"),
            mid=Decimal("100.00"),
            timestamp=datetime.now(UTC),
            source="test",
        )

        result = await svc.ingest(price)

        assert not result.accepted


class TestIngestionDedup:
    @pytest.mark.asyncio
    async def test_duplicate_within_window_skipped(self) -> None:
        svc, md = _make_service(dedup_window=5)
        now = datetime.now(UTC)
        p1 = make_price(instrument_id="AAPL", mid=Decimal("150.00"), timestamp=now)
        p2 = make_price(
            instrument_id="AAPL",
            mid=Decimal("150.50"),
            timestamp=now + timedelta(seconds=1),
        )

        r1 = await svc.ingest(p1)
        r2 = await svc.ingest(p2)

        assert r1.accepted
        assert not r2.accepted
        assert r2.reason == "duplicate"
        assert md.store_price.await_count == 1

    @pytest.mark.asyncio
    async def test_different_instruments_not_deduped(self) -> None:
        svc, md = _make_service(dedup_window=5)
        now = datetime.now(UTC)
        p1 = make_price(instrument_id="AAPL", timestamp=now)
        p2 = make_price(instrument_id="MSFT", timestamp=now)

        r1 = await svc.ingest(p1)
        r2 = await svc.ingest(p2)

        assert r1.accepted
        assert r2.accepted
        assert md.store_price.await_count == 2

    @pytest.mark.asyncio
    async def test_outside_dedup_window_accepted(self) -> None:
        svc, md = _make_service(dedup_window=2)
        now = datetime.now(UTC)
        p1 = make_price(instrument_id="AAPL", timestamp=now)
        p2 = make_price(instrument_id="AAPL", timestamp=now + timedelta(seconds=3))

        r1 = await svc.ingest(p1)
        r2 = await svc.ingest(p2)

        assert r1.accepted
        assert r2.accepted

    @pytest.mark.asyncio
    async def test_batch_counts_duplicates(self) -> None:
        svc, _ = _make_service(dedup_window=5)
        now = datetime.now(UTC)
        prices = [
            make_price(instrument_id="AAPL", timestamp=now),
            make_price(instrument_id="AAPL", timestamp=now + timedelta(seconds=1)),
            make_price(instrument_id="MSFT", timestamp=now),
        ]

        result = await svc.ingest_batch(prices)

        assert result.accepted == 2
        assert result.duplicates == 1


class TestIngestionPublishing:
    @pytest.mark.asyncio
    async def test_publishes_event_when_bus_configured(self) -> None:
        bus = InProcessEventBus()
        captured: list = []

        async def capture(event):
            captured.append(event)

        bus.subscribe("prices.normalized", capture)
        svc, _ = _make_service(event_bus=bus)
        price = make_price(instrument_id="AAPL")

        await svc.ingest(price)

        assert len(captured) == 1
        assert captured[0].event_type == "prices.normalized"
        assert captured[0].data["instrument_id"] == "AAPL"

    @pytest.mark.asyncio
    async def test_no_publish_without_bus(self) -> None:
        svc, _ = _make_service(event_bus=None)
        price = make_price(instrument_id="AAPL")

        result = await svc.ingest(price)

        assert result.accepted  # still accepted, just not published
