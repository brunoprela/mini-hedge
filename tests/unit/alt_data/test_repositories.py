"""Unit tests for alt_data repositories."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.alt_data.repositories.alt_data_feed import AltDataFeedRepository
from app.modules.alt_data.repositories.alt_data_point import AltDataPointRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    return session


def _make_repo(repo_cls):
    session = _mock_session()
    factory = MagicMock()

    @asynccontextmanager
    async def _fake_factory():
        yield session

    factory.side_effect = _fake_factory
    repo = repo_cls(session_factory=factory)
    return repo, session


# ---------------------------------------------------------------------------
# AltDataFeedRepository
# ---------------------------------------------------------------------------


class TestAltDataFeedRepoInsertFeed:
    @pytest.mark.asyncio
    async def test_adds_and_commits(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        record = MagicMock()

        await repo.insert_feed(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_explicit_session(self) -> None:
        repo, _ = _make_repo(AltDataFeedRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.insert_feed(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.commit.assert_awaited_once()


class TestAltDataFeedRepoGetFeed:
    @pytest.mark.asyncio
    async def test_returns_record_when_found(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        expected = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_feed("some-id")

        assert result is expected
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_feed("missing-id")

        assert result is None


class TestAltDataFeedRepoGetFeedByName:
    @pytest.mark.asyncio
    async def test_returns_record_by_name(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        expected = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_feed_by_name("my-feed")

        assert result is expected
        session.execute.assert_awaited_once()


class TestAltDataFeedRepoListFeeds:
    @pytest.mark.asyncio
    async def test_returns_list_of_feeds(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        records = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_feeds()

        assert result == records

    @pytest.mark.asyncio
    async def test_filters_by_source(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await repo.list_feeds(source="satellite")

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_inactive_feeds_included_when_flag_false(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await repo.list_feeds(active_only=False)

        session.execute.assert_awaited_once()


class TestAltDataFeedRepoUpdateFeed:
    @pytest.mark.asyncio
    async def test_updates_last_updated(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        session.execute = AsyncMock()

        await repo.update_feed("feed-1", last_updated=NOW)

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_record_count(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        session.execute = AsyncMock()

        await repo.update_feed("feed-1", record_count=42)

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_noop_when_no_values(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        session.execute = AsyncMock()

        await repo.update_feed("feed-1")

        # No values means no execute/commit
        session.execute.assert_not_awaited()
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_updates_both_fields(self) -> None:
        repo, session = _make_repo(AltDataFeedRepository)
        session.execute = AsyncMock()

        await repo.update_feed("feed-1", last_updated=NOW, record_count=10)

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# AltDataPointRepository
# ---------------------------------------------------------------------------


class TestAltDataPointRepoInsertDataPoints:
    @pytest.mark.asyncio
    async def test_adds_all_and_commits(self) -> None:
        repo, session = _make_repo(AltDataPointRepository)
        records = [MagicMock(), MagicMock()]

        await repo.insert_data_points(records)

        session.add_all.assert_called_once_with(records)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_explicit_session(self) -> None:
        repo, _ = _make_repo(AltDataPointRepository)
        explicit = _mock_session()
        records = [MagicMock()]

        await repo.insert_data_points(records, session=explicit)

        explicit.add_all.assert_called_once_with(records)
        explicit.commit.assert_awaited_once()


class TestAltDataPointRepoGetDataPoints:
    @pytest.mark.asyncio
    async def test_returns_data_points(self) -> None:
        repo, session = _make_repo(AltDataPointRepository)
        expected = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = expected
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_data_points("feed-1")

        assert result == expected

    @pytest.mark.asyncio
    async def test_filters_by_instrument_id(self) -> None:
        repo, session = _make_repo(AltDataPointRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await repo.get_data_points("feed-1", instrument_id="AAPL")

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filters_by_start_and_end(self) -> None:
        repo, session = _make_repo(AltDataPointRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await repo.get_data_points("feed-1", start=NOW, end=NOW)

        session.execute.assert_awaited_once()


class TestAltDataPointRepoGetLatestPoint:
    @pytest.mark.asyncio
    async def test_returns_latest_point(self) -> None:
        repo, session = _make_repo(AltDataPointRepository)
        expected = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_latest_point("feed-1")

        assert result is expected

    @pytest.mark.asyncio
    async def test_filters_by_instrument(self) -> None:
        repo, session = _make_repo(AltDataPointRepository)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_latest_point("feed-1", "AAPL")

        assert result is None
        session.execute.assert_awaited_once()


class TestAltDataPointRepoGetSummary:
    @pytest.mark.asyncio
    async def test_returns_summary_dict(self) -> None:
        repo, session = _make_repo(AltDataPointRepository)
        row = MagicMock()
        row.data_points = 100
        row.avg_value = Decimal("50.5")
        row.min_value = Decimal("10.0")
        row.max_value = Decimal("90.0")
        row.coverage_start = NOW
        row.coverage_end = NOW
        mock_result = MagicMock()
        mock_result.one.return_value = row
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_summary("feed-1")

        assert result["data_points"] == 100
        assert result["avg_value"] == Decimal("50.5")
        assert result["min_value"] == Decimal("10.0")
        assert result["max_value"] == Decimal("90.0")
        assert result["coverage_start"] is NOW
        assert result["coverage_end"] is NOW
