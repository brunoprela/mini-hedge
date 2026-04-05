"""Mock-exchange market data adapter — bridges external vendor Kafka to internal event bus.

The mock-exchange is an external service with its own Kafka cluster.
This adapter consumes JSON price events from the vendor's Kafka,
translates them into the platform's internal BaseEvent format, and
re-publishes to the internal event bus (Avro-encoded).

This is the same pattern a Bloomberg BLPAPI or LSEG RDP adapter would use:
consume from the vendor feed, normalize, inject into our internal bus.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING

import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from app.shared.events import BaseEvent
from app.shared.schema_registry import shared_topic

if TYPE_CHECKING:
    from app.shared.events import EventBus

logger = structlog.get_logger()

# Topic on the external vendor's Kafka cluster
_EXTERNAL_PRICES_TOPIC = "shared.prices.normalized"


class MockExchangeMarketDataAdapter:
    """MarketDataAdapter that bridges mock-exchange's Kafka feed to the internal event bus.

    Connects to the vendor's Kafka cluster (separate from platform's),
    consumes JSON-encoded price events, and re-publishes them as
    Avro-encoded events on the platform's internal Kafka.
    """

    def __init__(
        self,
        *,
        base_url: str,
        kafka_bootstrap_servers: str,
        event_bus: EventBus,
    ) -> None:
        self._base_url = base_url
        self._kafka_servers = kafka_bootstrap_servers
        self._event_bus = event_bus
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start_streaming(self, instruments: list[str]) -> None:
        """Start consuming prices from the external vendor's Kafka and bridging to internal bus."""
        self._running = True
        self._task = asyncio.create_task(
            self._consume_prices(),
            name="mock-exchange-price-bridge",
        )
        logger.info(
            "mock_exchange_market_data_started",
            kafka=self._kafka_servers,
            instruments=len(instruments),
        )

    async def stop_streaming(self) -> None:
        """Stop the external Kafka consumer."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("mock_exchange_market_data_stopped")

    async def _consume_prices(self) -> None:
        """Consume price events from the external vendor's Kafka and bridge them."""
        consumer = AIOKafkaConsumer(
            _EXTERNAL_PRICES_TOPIC,
            bootstrap_servers=self._kafka_servers,
            group_id="minihedge-external-market-data",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await consumer.start()

        try:
            while self._running:
                try:
                    msg_batch = await consumer.getmany(timeout_ms=1000, max_records=10)
                except KafkaError:
                    logger.exception("external_kafka_poll_error")
                    await asyncio.sleep(1)
                    continue

                for _tp, messages in msg_batch.items():
                    for msg in messages:
                        if msg.value is None:
                            continue
                        try:
                            await self._bridge_price_event(msg.value)
                        except Exception:
                            logger.exception("price_bridge_failed")
        finally:
            await consumer.stop()

    async def _bridge_price_event(self, raw: bytes) -> None:
        """Decode a JSON envelope from the vendor and re-publish as an internal event."""
        envelope = json.loads(raw)
        from datetime import datetime as dt

        event = BaseEvent(
            event_id=envelope["event_id"],
            event_type=envelope["event_type"],
            event_version=envelope.get("event_version", 1),
            timestamp=dt.fromisoformat(envelope["timestamp"]),
            data=envelope["data"],
            actor_id=envelope.get("actor_id"),
            actor_type=envelope.get("actor_type"),
            fund_slug=envelope.get("fund_slug"),
        )
        await self._event_bus.publish(shared_topic("prices.normalized"), event)
