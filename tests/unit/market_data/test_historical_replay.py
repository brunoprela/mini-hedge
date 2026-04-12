"""Unit tests for HistoricalReplayService."""

from __future__ import annotations

import csv
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.modules.market_data.core.historical_replay import (
    HistoricalReplayService,
    ReplayConfig,
    ReplayResult,
    ReplaySpeed,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Helper to write a CSV test fixture."""
    fieldnames = ["timestamp", "instrument_id", "bid", "ask", "mid", "volume"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestReplaySpeed:
    def test_enum_values(self) -> None:
        assert ReplaySpeed.REAL_TIME == "real_time"
        assert ReplaySpeed.FAST_10X == "fast_10x"
        assert ReplaySpeed.FAST_100X == "fast_100x"
        assert ReplaySpeed.MAX_SPEED == "max_speed"


class TestReplayConfig:
    def test_defaults(self) -> None:
        config = ReplayConfig()
        assert config.speed == ReplaySpeed.MAX_SPEED
        assert config.max_events_per_second == 10_000
        assert config.publish_topic == "shared.prices.normalized"


class TestCSVReplay:
    @pytest.mark.asyncio
    async def test_replay_valid_csv(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "prices.csv"
        _write_csv(csv_file, [
            {
                "timestamp": "2026-04-12T10:00:00+00:00",
                "instrument_id": "AAPL",
                "bid": "149.50",
                "ask": "150.50",
                "mid": "150.00",
                "volume": "1000",
            },
            {
                "timestamp": "2026-04-12T10:01:00+00:00",
                "instrument_id": "MSFT",
                "bid": "399.00",
                "ask": "401.00",
                "mid": "400.00",
                "volume": "500",
            },
        ])

        event_bus = AsyncMock()
        config = ReplayConfig(speed=ReplaySpeed.MAX_SPEED, max_events_per_second=0)
        service = HistoricalReplayService(event_bus=event_bus, config=config)

        result = await service.replay_from_csv(csv_file)

        assert result.events_published == 2
        assert result.events_skipped == 0
        assert result.source == f"csv:{csv_file.name}"
        assert event_bus.publish.await_count == 2

    @pytest.mark.asyncio
    async def test_replay_csv_with_bad_rows(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "bad.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "instrument_id", "bid", "ask", "mid", "volume"])
            writer.writerow(["2026-04-12T10:00:00+00:00", "AAPL", "150", "151", "150.5", "1000"])
            writer.writerow(["bad-timestamp", "MSFT", "400", "401", "400.5", "500"])

        event_bus = AsyncMock()
        config = ReplayConfig(speed=ReplaySpeed.MAX_SPEED, max_events_per_second=0)
        service = HistoricalReplayService(event_bus=event_bus, config=config)

        result = await service.replay_from_csv(csv_file)

        assert result.events_published == 1
        assert result.events_skipped == 1

    @pytest.mark.asyncio
    async def test_replay_csv_file_not_found(self) -> None:
        event_bus = AsyncMock()
        service = HistoricalReplayService(event_bus=event_bus)

        with pytest.raises(FileNotFoundError):
            await service.replay_from_csv(Path("/nonexistent/file.csv"))

    @pytest.mark.asyncio
    async def test_replay_csv_empty_file(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "empty.csv"
        with csv_file.open("w") as f:
            f.write("timestamp,instrument_id,bid,ask,mid,volume\n")

        event_bus = AsyncMock()
        config = ReplayConfig(speed=ReplaySpeed.MAX_SPEED, max_events_per_second=0)
        service = HistoricalReplayService(event_bus=event_bus, config=config)

        result = await service.replay_from_csv(csv_file)
        assert result.events_published == 0

    @pytest.mark.asyncio
    async def test_replay_publishes_correct_event_data(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "single.csv"
        _write_csv(csv_file, [
            {
                "timestamp": "2026-04-12T10:00:00+00:00",
                "instrument_id": "AAPL",
                "bid": "149.50",
                "ask": "150.50",
                "mid": "150.00",
                "volume": "1000",
            },
        ])

        event_bus = AsyncMock()
        config = ReplayConfig(speed=ReplaySpeed.MAX_SPEED, max_events_per_second=0)
        service = HistoricalReplayService(event_bus=event_bus, config=config)

        await service.replay_from_csv(csv_file)

        call_args = event_bus.publish.call_args
        topic = call_args[0][0]
        event = call_args[0][1]
        assert topic == "shared.prices.normalized"
        assert event.event_type == "prices.normalized"
        assert event.data["instrument_id"] == "AAPL"
        assert event.data["bid"] == "149.50"
        assert event.data["ask"] == "150.50"
        assert event.data["mid"] == "150.00"
        assert event.data["volume"] == 1000


class TestReplayResult:
    def test_dataclass_fields(self) -> None:
        result = ReplayResult(
            events_published=100,
            events_skipped=5,
            duration_seconds=1.5,
            source="csv:test.csv",
        )
        assert result.events_published == 100
        assert result.events_skipped == 5
        assert result.duration_seconds == 1.5
        assert result.source == "csv:test.csv"
