"""Historical replay service — replays recorded price data at configurable speed.

Supports three data sources:
- CSV files (timestamp, instrument_id, bid, ask, mid, volume)
- Yahoo Finance (yfinance) — daily OHLCV bars
- Pre-seeded TimescaleDB — full tick data from previous recording sessions

Replayed prices are published to a Kafka topic (typically ``prices.normalized``)
at the configured speed multiplier, respecting inter-tick timing for realistic
simulation.
"""

from __future__ import annotations

import asyncio
import csv
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.events import EventBus

logger = structlog.get_logger()


class ReplaySpeed(StrEnum):
    """Speed multiplier for historical replay."""

    REAL_TIME = "real_time"  # 1x
    FAST_10X = "fast_10x"  # 10x
    FAST_100X = "fast_100x"  # 100x
    MAX_SPEED = "max_speed"  # as fast as possible with throttling


_SPEED_MULTIPLIERS: dict[ReplaySpeed, float] = {
    ReplaySpeed.REAL_TIME: 1.0,
    ReplaySpeed.FAST_10X: 10.0,
    ReplaySpeed.FAST_100X: 100.0,
    ReplaySpeed.MAX_SPEED: 0.0,  # no delay
}


@dataclass(frozen=True)
class ReplayResult:
    """Summary of a replay session."""

    events_published: int
    events_skipped: int = 0
    duration_seconds: float = 0.0
    source: str = ""


@dataclass
class ReplayConfig:
    """Configuration for a replay session."""

    speed: ReplaySpeed = ReplaySpeed.MAX_SPEED
    max_events_per_second: int = 10_000
    publish_topic: str = "shared.prices.normalized"


class HistoricalReplayService:
    """Replays historical price data from multiple sources."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        config: ReplayConfig | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config = config or ReplayConfig()
        self._throttle_interval = (
            1.0 / self._config.max_events_per_second
            if self._config.max_events_per_second > 0
            else 0.0
        )

    async def replay_from_csv(self, csv_path: Path) -> ReplayResult:
        """Replay price data from a CSV file.

        Expected columns: timestamp, instrument_id, bid, ask, mid, volume.
        Returns number of events published.
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        start_time = time.monotonic()
        published = 0
        skipped = 0
        prev_ts: datetime | None = None
        multiplier = _SPEED_MULTIPLIERS[self._config.speed]

        with csv_path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts = datetime.fromisoformat(row["timestamp"])
                    instrument_id = row["instrument_id"]
                    bid = Decimal(row.get("bid", "0"))
                    ask = Decimal(row.get("ask", "0"))
                    mid = Decimal(row.get("mid", "0"))
                    volume = int(row.get("volume", "0"))
                except (KeyError, ValueError, InvalidOperation) as exc:
                    logger.warning("csv_row_skipped", error=str(exc))
                    skipped += 1
                    continue

                # Inter-tick delay for speed simulation
                if prev_ts is not None and multiplier > 0:
                    delta = (ts - prev_ts).total_seconds()
                    if delta > 0:
                        await asyncio.sleep(delta / multiplier)
                prev_ts = ts

                # Throttle to max_events_per_second
                if self._throttle_interval > 0:
                    await asyncio.sleep(self._throttle_interval)

                event = self._make_price_event(instrument_id, bid, ask, mid, volume, ts)
                await self._event_bus.publish(self._config.publish_topic, event)
                published += 1

        duration = time.monotonic() - start_time
        logger.info(
            "csv_replay_complete",
            path=str(csv_path),
            published=published,
            skipped=skipped,
            duration=f"{duration:.2f}s",
        )
        return ReplayResult(
            events_published=published,
            events_skipped=skipped,
            duration_seconds=duration,
            source=f"csv:{csv_path.name}",
        )

    async def replay_from_yfinance(
        self,
        tickers: list[str],
        start: str,
        end: str,
    ) -> ReplayResult:
        """Replay daily OHLCV bars from Yahoo Finance.

        Downloads data via yfinance and publishes each bar as a price event.
        Sequential download with backoff to handle rate limiting.
        """
        try:
            import yfinance as yf  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "yfinance is required for Yahoo Finance replay. "
                "Install it with: pip install yfinance"
            ) from None

        start_time = time.monotonic()
        published = 0
        skipped = 0

        for ticker in tickers:
            try:
                data = yf.download(
                    ticker,
                    start=start,
                    end=end,
                    progress=False,
                    auto_adjust=True,
                )
                if data.empty:
                    logger.warning("yfinance_no_data", ticker=ticker)
                    skipped += 1
                    continue

                for ts, row in data.iterrows():
                    mid = Decimal(str(row["Close"]))
                    volume = int(row["Volume"])
                    # Use mid as both bid/ask for daily bars
                    event = self._make_price_event(
                        ticker, mid, mid, mid, volume,
                        ts.to_pydatetime().replace(tzinfo=UTC),
                    )
                    await self._event_bus.publish(self._config.publish_topic, event)
                    published += 1

                    if self._throttle_interval > 0:
                        await asyncio.sleep(self._throttle_interval)

            except Exception:
                logger.exception("yfinance_download_failed", ticker=ticker)
                skipped += 1
                # Backoff before next ticker
                await asyncio.sleep(2.0)

        duration = time.monotonic() - start_time
        logger.info(
            "yfinance_replay_complete",
            tickers=len(tickers),
            published=published,
            skipped=skipped,
            duration=f"{duration:.2f}s",
        )
        return ReplayResult(
            events_published=published,
            events_skipped=skipped,
            duration_seconds=duration,
            source="yfinance",
        )

    async def replay_from_timescaledb(
        self,
        session: AsyncSession,
        instrument_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReplayResult:
        """Replay tick data from the prices hypertable.

        Reads historical prices from TimescaleDB and re-publishes them.
        Useful for re-running simulations against previously recorded data.
        """
        from sqlalchemy import text

        start_time = time.monotonic()
        published = 0
        prev_ts: datetime | None = None
        multiplier = _SPEED_MULTIPLIERS[self._config.speed]

        # Stream prices ordered by timestamp for correct replay ordering
        query = text("""
            SELECT timestamp, instrument_id, bid, ask, mid, volume
            FROM market_data.prices
            WHERE instrument_id = ANY(:ids)
              AND timestamp BETWEEN :start AND :end
            ORDER BY timestamp
        """)

        result = await session.execute(
            query,
            {"ids": instrument_ids, "start": start, "end": end},
        )

        for row in result:
            ts = row.timestamp
            instrument_id = row.instrument_id
            bid = Decimal(str(row.bid)) if row.bid else Decimal(0)
            ask = Decimal(str(row.ask)) if row.ask else Decimal(0)
            mid = Decimal(str(row.mid)) if row.mid else Decimal(0)
            volume = int(row.volume) if row.volume else 0

            # Inter-tick delay
            if prev_ts is not None and multiplier > 0:
                delta = (ts - prev_ts).total_seconds()
                if delta > 0:
                    await asyncio.sleep(delta / multiplier)
            prev_ts = ts

            if self._throttle_interval > 0:
                await asyncio.sleep(self._throttle_interval)

            event = self._make_price_event(instrument_id, bid, ask, mid, volume, ts)
            await self._event_bus.publish(self._config.publish_topic, event)
            published += 1

        duration = time.monotonic() - start_time
        logger.info(
            "timescaledb_replay_complete",
            instruments=len(instrument_ids),
            published=published,
            duration=f"{duration:.2f}s",
        )
        return ReplayResult(
            events_published=published,
            duration_seconds=duration,
            source="timescaledb",
        )

    @staticmethod
    def _make_price_event(
        instrument_id: str,
        bid: Decimal,
        ask: Decimal,
        mid: Decimal,
        volume: int,
        timestamp: datetime,
    ) -> BaseEvent:
        return BaseEvent(
            event_type="prices.normalized",
            data={
                "instrument_id": instrument_id,
                "bid": str(bid),
                "ask": str(ask),
                "mid": str(mid),
                "volume": volume,
                "timestamp": timestamp.isoformat(),
            },
            timestamp=timestamp,
        )
