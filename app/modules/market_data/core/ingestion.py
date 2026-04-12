"""Market data ingestion pipeline — validate, deduplicate, store, publish.

The ``MarketDataIngestionService`` is the single entry point for all incoming
price data regardless of vendor. Each price tick passes through:

1. **Validation** — PriceValidator checks positivity, spread, staleness, bid/ask ordering
2. **Deduplication** — skip if (instrument_id, timestamp, source) was already seen recently
3. **Storage** — persist to the prices hypertable via PriceRepository (ON CONFLICT DO NOTHING)
4. **Cache update** — update the in-memory latest-price cache
5. **Feed health** — record the update in FeedHealthMonitor
6. **Publish** — emit ``prices.normalized`` event for downstream consumers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.market_data.core.feed_health import FeedHealthMonitor
from app.modules.market_data.core.price_validator import PriceValidationReport, PriceValidator
from app.modules.market_data.interfaces import PriceSnapshot

if TYPE_CHECKING:
    from app.modules.market_data.services import MarketDataService
    from app.shared.events import BaseEvent, EventBus

logger = structlog.get_logger()


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of ingesting a single price tick."""

    instrument_id: str
    accepted: bool
    reason: str = "ok"
    validation_report: PriceValidationReport | None = None


@dataclass(frozen=True)
class IngestionBatchResult:
    """Outcome of ingesting a batch of price ticks."""

    total: int
    accepted: int
    rejected: int
    duplicates: int
    results: list[IngestionResult] = field(default_factory=list)


class MarketDataIngestionService:
    """Multi-vendor price ingestion with validate/dedup/store/publish pipeline."""

    def __init__(
        self,
        *,
        market_data_service: MarketDataService,
        validator: PriceValidator | None = None,
        feed_monitor: FeedHealthMonitor | None = None,
        event_bus: EventBus | None = None,
        publish_topic: str = "prices.normalized",
        dedup_window_seconds: int = 1,
    ) -> None:
        self._service = market_data_service
        self._validator = validator or PriceValidator()
        self._feed_monitor = feed_monitor or FeedHealthMonitor()
        self._event_bus = event_bus
        self._publish_topic = publish_topic
        self._dedup_window = dedup_window_seconds
        # Simple in-memory dedup: (instrument_id, source) → last accepted timestamp
        self._seen: dict[tuple[str, str], datetime] = {}

    def _is_duplicate(self, snapshot: PriceSnapshot) -> bool:
        """Check if this tick is a duplicate within the dedup window."""
        key = (snapshot.instrument_id, snapshot.source)
        last_ts = self._seen.get(key)
        if last_ts is not None:
            delta = abs((snapshot.timestamp - last_ts).total_seconds())
            if delta < self._dedup_window:
                return True
        return False

    def _mark_seen(self, snapshot: PriceSnapshot) -> None:
        key = (snapshot.instrument_id, snapshot.source)
        self._seen[key] = snapshot.timestamp

    async def ingest(
        self,
        snapshot: PriceSnapshot,
    ) -> IngestionResult:
        """Ingest a single price tick through the full pipeline."""
        # 1. Validate
        report = self._validator.validate(
            instrument_id=snapshot.instrument_id,
            bid=snapshot.bid,
            ask=snapshot.ask,
            mid=snapshot.mid,
            timestamp=snapshot.timestamp,
        )
        if not report.valid:
            logger.warning(
                "price_validation_failed",
                instrument_id=snapshot.instrument_id,
                failures=[f.message for f in report.failures],
            )
            return IngestionResult(
                instrument_id=snapshot.instrument_id,
                accepted=False,
                reason="validation_failed",
                validation_report=report,
            )

        # 2. Deduplicate
        if self._is_duplicate(snapshot):
            return IngestionResult(
                instrument_id=snapshot.instrument_id,
                accepted=False,
                reason="duplicate",
            )

        # 3. Store
        await self._service.store_price(snapshot)
        self._mark_seen(snapshot)

        # 4. Cache update
        self._service.update_latest(snapshot)

        # 5. Feed health
        self._feed_monitor.record_update(
            instrument_id=snapshot.instrument_id,
            source=snapshot.source,
            timestamp=snapshot.timestamp,
            price=float(snapshot.mid),
        )

        # 6. Publish
        if self._event_bus is not None:
            await self._publish(snapshot)

        return IngestionResult(
            instrument_id=snapshot.instrument_id,
            accepted=True,
        )

    async def ingest_batch(
        self,
        snapshots: list[PriceSnapshot],
    ) -> IngestionBatchResult:
        """Ingest a batch of price ticks."""
        results: list[IngestionResult] = []
        accepted = 0
        rejected = 0
        duplicates = 0

        for snapshot in snapshots:
            result = await self.ingest(snapshot)
            results.append(result)
            if result.accepted:
                accepted += 1
            elif result.reason == "duplicate":
                duplicates += 1
            else:
                rejected += 1

        return IngestionBatchResult(
            total=len(snapshots),
            accepted=accepted,
            rejected=rejected,
            duplicates=duplicates,
            results=results,
        )

    async def _publish(self, snapshot: PriceSnapshot) -> None:
        """Emit a prices.normalized event."""
        from app.shared.events import BaseEvent

        event = BaseEvent(
            event_type="prices.normalized",
            data={
                "instrument_id": snapshot.instrument_id,
                "bid": str(snapshot.bid),
                "ask": str(snapshot.ask),
                "mid": str(snapshot.mid),
                "volume": str(snapshot.volume) if snapshot.volume is not None else None,
                "timestamp": snapshot.timestamp.isoformat(),
                "source": snapshot.source,
            },
        )
        await self._event_bus.publish(self._publish_topic, event)  # type: ignore[union-attr]

    async def publish_feed_status(self) -> None:
        """Publish a market-data.status event summarizing current feed health.

        Intended to be called periodically (e.g. every minute) by a background
        task or health-check endpoint. Publishes to shared.market-data.status.
        """
        if self._event_bus is None:
            return

        from app.shared.audit.events import AuditEventType
        from app.shared.events import BaseEvent
        from app.shared.schema_registry import shared_topic

        report = self._feed_monitor.check_health()
        event = BaseEvent(
            event_type=AuditEventType.MARKET_DATA_STATUS,
            data={
                "total_feeds": report.total_feeds,
                "healthy_feeds": report.healthy_feeds,
                "stale_feeds": report.stale_feeds,
                "stale_instruments": report.stale_instruments,
                "all_healthy": report.all_healthy,
                "checked_at": report.checked_at.isoformat(),
            },
        )
        await self._event_bus.publish(shared_topic("market-data.status"), event)

    @property
    def feed_monitor(self) -> FeedHealthMonitor:
        """Expose the feed health monitor for status queries."""
        return self._feed_monitor
