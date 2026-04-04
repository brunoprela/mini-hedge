"""Slim Kafka producer for mock-exchange.

Publishes events using the same Avro envelope schema as the main platform,
ensuring wire-format compatibility.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from confluent_kafka import Producer

logger = structlog.get_logger()


class MockExchangeProducer:
    """Publishes events to Kafka using JSON serialization.

    Uses the same topic names and event envelope as the platform.
    For dev simplicity we use JSON value serialization (not Avro) —
    the platform's price handler validates field presence, not schema ID.
    """

    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "linger.ms": 5,
            "compression.type": "snappy",
            "client.id": "mock-exchange",
        })

    def produce(self, topic: str, event_type: str, data: dict[str, Any]) -> None:
        envelope = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "event_version": 1,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data,
            "actor_id": None,
            "actor_type": None,
            "fund_slug": None,
        }
        self._producer.produce(
            topic=topic,
            value=json.dumps(envelope).encode("utf-8"),
            callback=self._delivery_callback,
        )

    def flush(self, timeout: float = 1.0) -> None:
        self._producer.flush(timeout)

    @staticmethod
    def _delivery_callback(err: Any, msg: Any) -> None:
        if err is not None:
            logger.error("kafka_delivery_failed", error=str(err), topic=msg.topic())
