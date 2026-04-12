"""Extended unit tests for AltDataService — covers list_feeds, get_feed_summary, and sentinel paths."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.alt_data.interfaces import (
    AltDataSource,
    DataFrequency,
    DataQuality,
)
from app.modules.alt_data.models.alt_data_feed import AltDataFeedRecord
from app.modules.alt_data.services import AltDataService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)


def _make_feed_record(**overrides) -> MagicMock:
    defaults = dict(
        id=str(uuid4()),
        name="test-feed",
        source=AltDataSource.SOCIAL_MEDIA.value,
        frequency=DataFrequency.DAILY.value,
        description="Test feed",
        instruments=["AAPL"],
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


def _make_service(
    *,
    feed_repo: AsyncMock | None = None,
    point_repo: AsyncMock | None = None,
    providers: list | None = None,
    event_bus=None,
) -> AltDataService:
    return AltDataService(
        feed_repo=feed_repo or AsyncMock(),
        point_repo=point_repo or AsyncMock(),
        providers=providers if providers is not None else [],
        session_factory=MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# list_feeds (lines 101-103)
# ---------------------------------------------------------------------------


class TestListFeeds:
    @pytest.mark.asyncio
    async def test_returns_feed_dtos(self) -> None:
        feed_repo = AsyncMock()
        r1 = _make_feed_record(name="feed-a")
        r2 = _make_feed_record(name="feed-b")
        feed_repo.list_feeds.return_value = [r1, r2]
        svc = _make_service(feed_repo=feed_repo)

        result = await svc.list_feeds()

        assert len(result) == 2
        assert result[0].name == "feed-a"
        assert result[1].name == "feed-b"

    @pytest.mark.asyncio
    async def test_passes_source_filter(self) -> None:
        feed_repo = AsyncMock()
        feed_repo.list_feeds.return_value = []
        svc = _make_service(feed_repo=feed_repo)

        await svc.list_feeds(source=AltDataSource.SATELLITE)

        _, kwargs = feed_repo.list_feeds.call_args
        assert kwargs["source"] == "satellite"

    @pytest.mark.asyncio
    async def test_none_source_passes_none(self) -> None:
        feed_repo = AsyncMock()
        feed_repo.list_feeds.return_value = []
        svc = _make_service(feed_repo=feed_repo)

        await svc.list_feeds(source=None)

        _, kwargs = feed_repo.list_feeds.call_args
        assert kwargs["source"] is None


# ---------------------------------------------------------------------------
# get_feed_summary (lines 181-191)
# ---------------------------------------------------------------------------


class TestGetFeedSummary:
    @pytest.mark.asyncio
    async def test_raises_when_feed_not_found(self) -> None:
        feed_repo = AsyncMock()
        feed_repo.get_feed.return_value = None
        svc = _make_service(feed_repo=feed_repo)

        with pytest.raises(ValueError, match="not found"):
            await svc.get_feed_summary(uuid4())

    @pytest.mark.asyncio
    async def test_returns_summary_with_stats(self) -> None:
        feed_id = uuid4()
        feed_repo = AsyncMock()
        point_repo = AsyncMock()
        feed_repo.get_feed.return_value = _make_feed_record(
            id=str(feed_id),
            name="sat-feed",
            source=AltDataSource.SATELLITE.value,
        )
        point_repo.get_summary.return_value = {
            "data_points": 50,
            "avg_value": Decimal("25.5"),
            "min_value": Decimal("10.0"),
            "max_value": Decimal("40.0"),
            "coverage_start": NOW,
            "coverage_end": NOW,
        }
        svc = _make_service(feed_repo=feed_repo, point_repo=point_repo)

        summary = await svc.get_feed_summary(feed_id)

        assert summary.feed_id == feed_id
        assert summary.feed_name == "sat-feed"
        assert summary.source == AltDataSource.SATELLITE
        assert summary.data_points == 50
        assert summary.avg_value == Decimal("25.5")
        assert summary.min_value == Decimal("10.0")
        assert summary.max_value == Decimal("40.0")
        assert summary.coverage_start == NOW.date()
        assert summary.coverage_end == NOW.date()

    @pytest.mark.asyncio
    async def test_summary_with_null_stats(self) -> None:
        feed_id = uuid4()
        feed_repo = AsyncMock()
        point_repo = AsyncMock()
        feed_repo.get_feed.return_value = _make_feed_record(id=str(feed_id))
        point_repo.get_summary.return_value = {
            "data_points": 0,
            "avg_value": None,
            "min_value": None,
            "max_value": None,
            "coverage_start": None,
            "coverage_end": None,
        }
        svc = _make_service(feed_repo=feed_repo, point_repo=point_repo)

        summary = await svc.get_feed_summary(feed_id)

        assert summary.data_points == 0
        assert summary.latest_value is None
        assert summary.avg_value is None
        assert summary.min_value is None
        assert summary.max_value is None
        assert summary.coverage_start is None
        assert summary.coverage_end is None


# ---------------------------------------------------------------------------
# collect_sentiment — provider returns None (line 222)
# ---------------------------------------------------------------------------


class TestCollectSentimentProviderNone:
    @pytest.mark.asyncio
    async def test_skips_when_provider_returns_none(self) -> None:
        provider = AsyncMock()
        provider.get_sentiment = AsyncMock(return_value=None)
        svc = _make_service(providers=[provider])

        results = await svc.collect_sentiment(["AAPL", "MSFT"])

        assert results == []
        assert provider.get_sentiment.call_count == 2
