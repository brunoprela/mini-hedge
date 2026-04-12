"""Extended tests for HistoricalReplayService — yfinance + TimescaleDB replay."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.market_data.core.historical_replay import (
    HistoricalReplayService,
    ReplayConfig,
    ReplaySpeed,
)


def _make_service(
    speed: ReplaySpeed = ReplaySpeed.MAX_SPEED,
    max_eps: int = 0,
) -> tuple[HistoricalReplayService, AsyncMock]:
    event_bus = AsyncMock()
    config = ReplayConfig(speed=speed, max_events_per_second=max_eps)
    svc = HistoricalReplayService(event_bus=event_bus, config=config)
    return svc, event_bus


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = ["timestamp", "instrument_id", "bid", "ask", "mid", "volume"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# CSV replay — inter-tick delay path (lines 121-124)
# ---------------------------------------------------------------------------

class TestCSVReplayWithDelay:
    @pytest.mark.asyncio
    async def test_real_time_speed_triggers_inter_tick_delay(self, tmp_path: Path) -> None:
        """With REAL_TIME speed, successive ticks with different timestamps trigger asyncio.sleep."""
        csv_file = tmp_path / "timed.csv"
        _write_csv(csv_file, [
            {
                "timestamp": "2026-04-12T10:00:00+00:00",
                "instrument_id": "AAPL",
                "bid": "150", "ask": "151", "mid": "150.5", "volume": "100",
            },
            {
                "timestamp": "2026-04-12T10:00:10+00:00",
                "instrument_id": "AAPL",
                "bid": "151", "ask": "152", "mid": "151.5", "volume": "200",
            },
        ])
        svc, event_bus = _make_service(speed=ReplaySpeed.REAL_TIME, max_eps=0)

        with patch("app.modules.market_data.core.historical_replay.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await svc.replay_from_csv(csv_file)

        assert result.events_published == 2
        # Should have slept for the 10-second delta / 1x multiplier = 10s
        mock_sleep.assert_called()
        delay_arg = mock_sleep.call_args[0][0]
        assert delay_arg == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_throttle_interval_triggers_sleep(self, tmp_path: Path) -> None:
        """When max_events_per_second > 0, each tick gets a throttle sleep."""
        csv_file = tmp_path / "throttled.csv"
        _write_csv(csv_file, [
            {
                "timestamp": "2026-04-12T10:00:00+00:00",
                "instrument_id": "AAPL",
                "bid": "150", "ask": "151", "mid": "150.5", "volume": "100",
            },
        ])
        svc, _ = _make_service(speed=ReplaySpeed.MAX_SPEED, max_eps=1000)

        with patch("app.modules.market_data.core.historical_replay.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await svc.replay_from_csv(csv_file)

        assert result.events_published == 1
        mock_sleep.assert_called()


# ---------------------------------------------------------------------------
# Yahoo Finance replay (lines 161-220)
# ---------------------------------------------------------------------------

class TestYFinanceReplay:
    @pytest.mark.asyncio
    async def test_yfinance_import_error(self) -> None:
        """When yfinance is not installed, ImportError is raised."""
        svc, _ = _make_service()
        with patch.dict("sys.modules", {"yfinance": None}):
            with pytest.raises(ImportError, match="yfinance is required"):
                await svc.replay_from_yfinance(["AAPL"], "2026-01-01", "2026-01-31")

    @pytest.mark.asyncio
    async def test_yfinance_successful_replay(self) -> None:
        """Successful yfinance download publishes events."""
        mock_yf = MagicMock()
        # Mock a DataFrame-like object with .empty and .iterrows()
        mock_df = MagicMock()
        mock_df.empty = False

        ts1 = MagicMock()
        ts1.to_pydatetime.return_value = datetime(2026, 1, 2)
        row1 = {"Close": 150.0, "Volume": 1000}

        ts2 = MagicMock()
        ts2.to_pydatetime.return_value = datetime(2026, 1, 3)
        row2 = {"Close": 152.0, "Volume": 2000}

        mock_df.iterrows.return_value = [(ts1, row1), (ts2, row2)]
        mock_yf.download.return_value = mock_df

        svc, event_bus = _make_service()

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            result = await svc.replay_from_yfinance(["AAPL"], "2026-01-01", "2026-01-31")

        assert result.events_published == 2
        assert result.events_skipped == 0
        assert result.source == "yfinance"
        assert event_bus.publish.await_count == 2

    @pytest.mark.asyncio
    async def test_yfinance_empty_data_skips_ticker(self) -> None:
        """If yfinance returns empty DataFrame, ticker is skipped."""
        mock_yf = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = True
        mock_yf.download.return_value = mock_df

        svc, event_bus = _make_service()

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            result = await svc.replay_from_yfinance(["FAKE"], "2026-01-01", "2026-01-31")

        assert result.events_published == 0
        assert result.events_skipped == 1

    @pytest.mark.asyncio
    async def test_yfinance_download_exception_skips_ticker(self) -> None:
        """If download raises, ticker is skipped and backoff sleep happens."""
        mock_yf = MagicMock()
        mock_yf.download.side_effect = RuntimeError("network error")

        svc, _ = _make_service()

        with (
            patch.dict("sys.modules", {"yfinance": mock_yf}),
            patch("app.modules.market_data.core.historical_replay.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            result = await svc.replay_from_yfinance(["FAIL"], "2026-01-01", "2026-01-31")

        assert result.events_published == 0
        assert result.events_skipped == 1
        # Backoff sleep of 2.0s
        mock_sleep.assert_called_with(2.0)

    @pytest.mark.asyncio
    async def test_yfinance_with_throttle(self) -> None:
        """Throttle interval is respected during yfinance replay."""
        mock_yf = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        ts1 = MagicMock()
        ts1.to_pydatetime.return_value = datetime(2026, 1, 2)
        mock_df.iterrows.return_value = [(ts1, {"Close": 150.0, "Volume": 1000})]
        mock_yf.download.return_value = mock_df

        svc, _ = _make_service(max_eps=500)

        with (
            patch.dict("sys.modules", {"yfinance": mock_yf}),
            patch("app.modules.market_data.core.historical_replay.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await svc.replay_from_yfinance(["AAPL"], "2026-01-01", "2026-01-31")

        assert result.events_published == 1


# ---------------------------------------------------------------------------
# TimescaleDB replay (lines 234-288)
# ---------------------------------------------------------------------------

class TestTimescaleDBReplay:
    @pytest.mark.asyncio
    async def test_replays_rows_from_db(self) -> None:
        """Rows from the DB are replayed as events."""
        row1 = SimpleNamespace(
            timestamp=datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC),
            instrument_id="AAPL",
            bid=Decimal("149"), ask=Decimal("151"), mid=Decimal("150"), volume=1000,
        )
        row2 = SimpleNamespace(
            timestamp=datetime(2026, 1, 2, 10, 0, 1, tzinfo=UTC),
            instrument_id="AAPL",
            bid=Decimal("150"), ask=Decimal("152"), mid=Decimal("151"), volume=2000,
        )

        session = AsyncMock()
        session.execute = AsyncMock(return_value=[row1, row2])

        svc, event_bus = _make_service()
        result = await svc.replay_from_timescaledb(
            session,
            ["AAPL"],
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 3, tzinfo=UTC),
        )

        assert result.events_published == 2
        assert result.source == "timescaledb"
        assert event_bus.publish.await_count == 2

    @pytest.mark.asyncio
    async def test_replays_with_none_fields(self) -> None:
        """Rows with None bid/ask/mid/volume default to zero."""
        row = SimpleNamespace(
            timestamp=datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC),
            instrument_id="MSFT",
            bid=None, ask=None, mid=None, volume=None,
        )

        session = AsyncMock()
        session.execute = AsyncMock(return_value=[row])

        svc, event_bus = _make_service()
        result = await svc.replay_from_timescaledb(
            session,
            ["MSFT"],
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 3, tzinfo=UTC),
        )

        assert result.events_published == 1
        # Check the event data has zeros
        call_args = event_bus.publish.call_args
        event = call_args[0][1]
        assert event.data["bid"] == "0"
        assert event.data["volume"] == 0

    @pytest.mark.asyncio
    async def test_replays_empty_result(self) -> None:
        """No rows from DB yields zero events."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=[])

        svc, _ = _make_service()
        result = await svc.replay_from_timescaledb(
            session,
            ["AAPL"],
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 3, tzinfo=UTC),
        )

        assert result.events_published == 0

    @pytest.mark.asyncio
    async def test_real_time_speed_inter_tick_delay(self) -> None:
        """With REAL_TIME speed, inter-tick delays are applied."""
        row1 = SimpleNamespace(
            timestamp=datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC),
            instrument_id="AAPL",
            bid=Decimal("149"), ask=Decimal("151"), mid=Decimal("150"), volume=1000,
        )
        row2 = SimpleNamespace(
            timestamp=datetime(2026, 1, 2, 10, 0, 5, tzinfo=UTC),
            instrument_id="AAPL",
            bid=Decimal("150"), ask=Decimal("152"), mid=Decimal("151"), volume=2000,
        )

        session = AsyncMock()
        session.execute = AsyncMock(return_value=[row1, row2])

        svc, _ = _make_service(speed=ReplaySpeed.REAL_TIME)

        with patch("app.modules.market_data.core.historical_replay.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await svc.replay_from_timescaledb(
                session,
                ["AAPL"],
                datetime(2026, 1, 2, tzinfo=UTC),
                datetime(2026, 1, 3, tzinfo=UTC),
            )

        assert result.events_published == 2
        mock_sleep.assert_called()
        delay = mock_sleep.call_args[0][0]
        assert delay == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_throttle_interval_with_db_replay(self) -> None:
        """Throttle sleep is applied when max_events_per_second is set."""
        row = SimpleNamespace(
            timestamp=datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC),
            instrument_id="AAPL",
            bid=Decimal("149"), ask=Decimal("151"), mid=Decimal("150"), volume=1000,
        )

        session = AsyncMock()
        session.execute = AsyncMock(return_value=[row])

        svc, _ = _make_service(max_eps=500)

        with patch("app.modules.market_data.core.historical_replay.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await svc.replay_from_timescaledb(
                session,
                ["AAPL"],
                datetime(2026, 1, 2, tzinfo=UTC),
                datetime(2026, 1, 3, tzinfo=UTC),
            )

        assert result.events_published == 1
        mock_sleep.assert_called()
