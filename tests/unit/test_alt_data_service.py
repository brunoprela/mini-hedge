"""Unit tests for AltDataService — mocked repo, real event bus."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.adapters.mock_alt_data import MockAltDataProvider
from app.modules.alt_data.interface import (
    AltDataPoint,
    AltDataSource,
    DataFrequency,
    DataQuality,
)
from app.modules.alt_data.models import AltDataFeedRecord, AltDataPointRecord
from app.modules.alt_data.service import AltDataService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)
FEED_ID = str(uuid4())


def _make_feed_record(**overrides) -> MagicMock:
    defaults = dict(
        id=FEED_ID,
        name="test-feed",
        source=AltDataSource.SOCIAL_MEDIA.value,
        frequency=DataFrequency.DAILY.value,
        description="Test feed",
        instruments=["AAPL", "MSFT"],
        quality=DataQuality.RAW.value,
        is_active=True,
        last_updated=None,
        record_count=0,
        created_at=NOW,
    )
    defaults.update(overrides)
    record = MagicMock(spec=AltDataFeedRecord)
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _make_point_record(feed_id: str, instrument_id: str, value: Decimal) -> MagicMock:
    record = MagicMock(spec=AltDataPointRecord)
    record.feed_id = feed_id
    record.instrument_id = instrument_id
    record.timestamp = NOW
    record.value = value
    record.extra_metadata = {"source": "test"}
    return record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(event_bus, ["shared.audit"])
    return cap


@pytest.fixture
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def provider() -> MockAltDataProvider:
    return MockAltDataProvider()


@pytest.fixture
def service(
    repo: AsyncMock, provider: MockAltDataProvider, event_bus: InProcessEventBus
) -> AltDataService:
    return AltDataService(
        repo=repo,
        providers=[provider],
        session_factory=MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# create_feed
# ---------------------------------------------------------------------------


def _seed_feed_record(record, feed_id: str = FEED_ID) -> None:
    """Set server-side fields that would normally be set by PostgreSQL."""
    record.id = feed_id
    record.created_at = NOW


class TestCreateFeed:
    async def test_returns_feed_dto(self, service: AltDataService, repo: AsyncMock):
        repo.create_feed.side_effect = lambda r, **kw: _seed_feed_record(r)

        feed = await service.create_feed(
            name="satellite-ships",
            source=AltDataSource.SATELLITE,
            frequency=DataFrequency.DAILY,
            description="Ship tracking",
            instruments=["SHPG"],
        )

        assert feed.name == "satellite-ships"
        assert feed.source == AltDataSource.SATELLITE
        assert feed.frequency == DataFrequency.DAILY
        assert feed.quality == DataQuality.RAW
        assert feed.is_active is True

    async def test_publishes_audit_event(
        self, service: AltDataService, repo: AsyncMock, capture: EventCapture
    ):
        repo.create_feed.side_effect = lambda r, **kw: _seed_feed_record(r)

        await service.create_feed(
            name="web-sentiment",
            source=AltDataSource.WEB_SCRAPING,
            frequency=DataFrequency.HOURLY,
        )

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].data["name"] == "web-sentiment"

    async def test_empty_instruments_defaults_to_empty_list(
        self, service: AltDataService, repo: AsyncMock
    ):
        repo.create_feed.side_effect = lambda r, **kw: _seed_feed_record(r)

        feed = await service.create_feed(
            name="no-instruments",
            source=AltDataSource.PATENT_DATA,
            frequency=DataFrequency.MONTHLY,
        )

        assert feed.instruments == []


# ---------------------------------------------------------------------------
# ingest_data
# ---------------------------------------------------------------------------


class TestIngestData:
    async def test_returns_count_of_ingested_points(self, service: AltDataService, repo: AsyncMock):
        feed_id = uuid4()
        repo.get_feed.return_value = _make_feed_record(id=str(feed_id), record_count=0)

        points = [
            AltDataPoint(
                feed_id=feed_id,
                instrument_id="AAPL",
                timestamp=NOW,
                value=Decimal("42.5"),
            ),
            AltDataPoint(
                feed_id=feed_id,
                instrument_id="MSFT",
                timestamp=NOW,
                value=Decimal("77.1"),
            ),
        ]

        count = await service.ingest_data(feed_id, points)

        assert count == 2
        repo.insert_data_points.assert_called_once()

    async def test_publishes_audit_event_on_ingest(
        self, service: AltDataService, repo: AsyncMock, capture: EventCapture
    ):
        feed_id = uuid4()
        repo.get_feed.return_value = _make_feed_record(id=str(feed_id), record_count=5)

        points = [
            AltDataPoint(feed_id=feed_id, instrument_id="AAPL", timestamp=NOW, value=Decimal("1"))
        ]
        await service.ingest_data(feed_id, points)

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].data["data_points_ingested"] == 1
        assert audit_events[0].data["total_record_count"] == 6

    async def test_updates_feed_record_count(self, service: AltDataService, repo: AsyncMock):
        feed_id = uuid4()
        repo.get_feed.return_value = _make_feed_record(id=str(feed_id), record_count=10)

        points = [
            AltDataPoint(feed_id=feed_id, instrument_id=None, timestamp=NOW, value=Decimal("3"))
            for _ in range(5)
        ]
        await service.ingest_data(feed_id, points)

        repo.update_feed.assert_called_once()
        _, call_kwargs = repo.update_feed.call_args
        assert call_kwargs["record_count"] == 15


# ---------------------------------------------------------------------------
# query_data (get_feed_data)
# ---------------------------------------------------------------------------


class TestQueryData:
    async def test_returns_data_points(self, service: AltDataService, repo: AsyncMock):
        feed_id = uuid4()
        repo.get_data_points.return_value = [
            _make_point_record(str(feed_id), "AAPL", Decimal("100")),
            _make_point_record(str(feed_id), "AAPL", Decimal("102")),
        ]

        points = await service.get_feed_data(feed_id, instrument_id="AAPL")

        assert len(points) == 2
        assert all(p.instrument_id == "AAPL" for p in points)
        assert all(isinstance(p.value, Decimal) for p in points)

    async def test_metadata_mapped_from_extra_metadata(
        self, service: AltDataService, repo: AsyncMock
    ):
        feed_id = uuid4()
        pt = _make_point_record(str(feed_id), "TSLA", Decimal("200"))
        pt.extra_metadata = {"confidence": 0.9}
        repo.get_data_points.return_value = [pt]

        points = await service.get_feed_data(feed_id)

        assert points[0].metadata == {"confidence": 0.9}

    async def test_returns_empty_list_when_no_data(self, service: AltDataService, repo: AsyncMock):
        repo.get_data_points.return_value = []
        points = await service.get_feed_data(uuid4())
        assert points == []


# ---------------------------------------------------------------------------
# collect_sentiment (uses real MockAltDataProvider)
# ---------------------------------------------------------------------------


class TestCollectSentiment:
    async def test_returns_sentiment_for_each_instrument(self, service: AltDataService):
        results = await service.collect_sentiment(["AAPL", "MSFT", "TSLA"])

        assert len(results) == 3
        instruments = {r.instrument_id for r in results}
        assert instruments == {"AAPL", "MSFT", "TSLA"}

    async def test_sentiment_score_in_valid_range(self, service: AltDataService):
        results = await service.collect_sentiment(["AAPL"])
        score = results[0].sentiment_score
        assert Decimal("-1") <= score <= Decimal("1")

    async def test_no_providers_returns_empty(self, repo: AsyncMock, event_bus: InProcessEventBus):
        svc = AltDataService(repo=repo, providers=[], session_factory=MagicMock())
        results = await svc.collect_sentiment(["AAPL"])
        assert results == []
