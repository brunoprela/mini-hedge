"""Trade tape — rolling buffer of trade ticks with VWAP computation.

Stores per-instrument trade history and computes volume-weighted benchmarks
used by the TCA module on the platform side.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from mock_exchange.shared.models import TradeTick, VWAPData

if TYPE_CHECKING:
    from mock_exchange.shared.kafka import MockExchangeProducer

logger = structlog.get_logger()

TRADES_TOPIC = "market-data.trades"


class TradeTape:
    """Rolling buffer of trade ticks per instrument with VWAP queries."""

    def __init__(
        self,
        producer: MockExchangeProducer | None = None,
        max_ticks_per_instrument: int = 50_000,
        publish_ambient: bool = False,
    ) -> None:
        self._producer = producer
        self._max_ticks = max_ticks_per_instrument
        self._publish_ambient = publish_ambient
        self._ticks: dict[str, deque[TradeTick]] = defaultdict(
            lambda: deque(maxlen=self._max_ticks)
        )
        # Running daily volume counters
        self._daily_volume: dict[str, int] = defaultdict(int)

    def record_tick(self, tick: TradeTick) -> None:
        """Record a trade tick and optionally publish to Kafka."""
        self._ticks[tick.instrument_id].append(tick)
        self._daily_volume[tick.instrument_id] += tick.quantity

        # Publish real order ticks always; ambient only if configured
        if self._producer and (not tick.is_ambient or self._publish_ambient):
            self._producer.send(
                TRADES_TOPIC,
                key=tick.instrument_id,
                value={
                    "instrument_id": tick.instrument_id,
                    "price": str(tick.price),
                    "quantity": tick.quantity,
                    "side": tick.side,
                    "timestamp": tick.timestamp.isoformat(),
                    "is_ambient": tick.is_ambient,
                    "aggressor": tick.aggressor,
                },
            )

    def record_ticks(self, ticks: list[TradeTick]) -> None:
        """Record multiple ticks efficiently."""
        for tick in ticks:
            self.record_tick(tick)

    def vwap(
        self, instrument_id: str, start: datetime, end: datetime,
    ) -> VWAPData | None:
        """Compute VWAP for an instrument over a time window."""
        ticks = self._ticks.get(instrument_id)
        if not ticks:
            return None

        total_value = Decimal("0")
        total_volume = 0

        for tick in ticks:
            if tick.timestamp < start:
                continue
            if tick.timestamp > end:
                break
            total_value += tick.price * tick.quantity
            total_volume += tick.quantity

        if total_volume == 0:
            return None

        return VWAPData(
            instrument_id=instrument_id,
            vwap=(total_value / total_volume).quantize(Decimal("0.0001")),
            cumulative_volume=total_volume,
            period_start=start,
            period_end=end,
        )

    def volume_since(self, instrument_id: str, since: datetime) -> int:
        """Total volume traded since a timestamp."""
        ticks = self._ticks.get(instrument_id)
        if not ticks:
            return 0
        return sum(t.quantity for t in ticks if t.timestamp >= since)

    def arrival_price(self, instrument_id: str) -> Decimal | None:
        """Get the most recent trade price for an instrument."""
        ticks = self._ticks.get(instrument_id)
        if not ticks:
            return None
        return ticks[-1].price

    def recent_ticks(
        self, instrument_id: str, limit: int = 100,
    ) -> list[TradeTick]:
        """Return the most recent ticks for an instrument."""
        ticks = self._ticks.get(instrument_id)
        if not ticks:
            return []
        return list(ticks)[-limit:]

    def daily_volume(self, instrument_id: str) -> int:
        """Return cumulative volume for the current trading day."""
        return self._daily_volume.get(instrument_id, 0)

    def reset_daily_volumes(self) -> None:
        """Reset daily volume counters — called at start of each trading day."""
        self._daily_volume.clear()
