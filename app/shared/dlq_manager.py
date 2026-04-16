"""Dead letter queue management — inspect, peek, and replay failed events.

DLQ topics follow the naming convention ``{original_topic}.dlq``.
This module provides utilities to:
  - List all DLQ topics with message counts
  - Peek at messages in a DLQ topic (without consuming)
  - Replay messages back to their source topic
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import structlog
from aiokafka import (  # type: ignore[import-untyped]
    AIOKafkaConsumer,
    AIOKafkaProducer,
    TopicPartition,
)

logger = structlog.get_logger()


@dataclass
class DlqTopicInfo:
    """Summary of a single DLQ topic."""

    topic: str
    source_topic: str
    message_count: int


@dataclass
class DlqMessage:
    """A single message from a DLQ topic."""

    offset: int
    timestamp: int | None
    key: str | None
    value: dict[str, Any] | str


@dataclass
class ReplayResult:
    """Result of replaying DLQ messages."""

    topic: str
    source_topic: str
    replayed: int
    failed: int


class DlqManager:
    """Inspects and manages dead letter queue topics."""

    def __init__(self, bootstrap_servers: str) -> None:
        self._bootstrap_servers = bootstrap_servers

    async def list_topics(self) -> list[DlqTopicInfo]:
        """List all DLQ topics with approximate message counts."""
        consumer = AIOKafkaConsumer(
            bootstrap_servers=self._bootstrap_servers,
            group_id=None,
        )
        await consumer.start()

        try:
            all_topics = await consumer.topics()
            dlq_topics = sorted(t for t in all_topics if t.endswith(".dlq"))

            results: list[DlqTopicInfo] = []
            for topic in dlq_topics:
                partitions = consumer.partitions_for_topic(topic)
                if not partitions:
                    continue

                tps = [TopicPartition(topic, p) for p in partitions]
                end_offsets = await consumer.end_offsets(tps)
                beginning_offsets = await consumer.beginning_offsets(tps)

                count = sum(end_offsets.get(tp, 0) - beginning_offsets.get(tp, 0) for tp in tps)

                results.append(
                    DlqTopicInfo(
                        topic=topic,
                        source_topic=topic.removesuffix(".dlq"),
                        message_count=count,
                    )
                )

            return results
        finally:
            await consumer.stop()

    async def peek(self, topic: str, limit: int = 10) -> list[DlqMessage]:
        """Read messages from a DLQ topic without committing offsets."""
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=None,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        await consumer.start()

        try:
            messages: list[DlqMessage] = []
            batch = await consumer.getmany(timeout_ms=3000, max_records=limit)

            for _tp, msgs in batch.items():
                for msg in msgs:
                    value: dict[str, Any] | str
                    try:
                        value = json.loads(msg.value) if msg.value else ""
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        value = msg.value.decode("utf-8", errors="replace") if msg.value else ""

                    messages.append(
                        DlqMessage(
                            offset=msg.offset,
                            timestamp=msg.timestamp,
                            key=msg.key.decode("utf-8") if msg.key else None,
                            value=value,
                        )
                    )

            return messages
        finally:
            await consumer.stop()

    async def replay(self, topic: str, limit: int = 100) -> ReplayResult:
        """Replay DLQ messages back to the source topic.

        Consumes from the DLQ, publishes to the source topic, and commits.
        """
        source_topic = topic.removesuffix(".dlq")

        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id="minihedge-dlq-replay",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
        )

        await consumer.start()
        await producer.start()

        replayed = 0
        failed = 0

        try:
            batch = await consumer.getmany(timeout_ms=5000, max_records=limit)

            for _tp, msgs in batch.items():
                for msg in msgs:
                    try:
                        await producer.send(
                            topic=source_topic,
                            value=msg.value,
                            key=msg.key,
                        )
                        replayed += 1
                    except Exception:
                        logger.exception(
                            "dlq_replay_failed",
                            topic=topic,
                            offset=msg.offset,
                        )
                        failed += 1

            if batch and failed == 0:
                await consumer.commit()

            logger.info(
                "dlq_replay_complete",
                topic=topic,
                source_topic=source_topic,
                replayed=replayed,
                failed=failed,
            )

            return ReplayResult(
                topic=topic,
                source_topic=source_topic,
                replayed=replayed,
                failed=failed,
            )
        finally:
            await producer.stop()
            await consumer.stop()
