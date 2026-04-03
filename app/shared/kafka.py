"""Kafka event bus — implements the ``EventBus`` protocol over Confluent Kafka.

Produces events as Avro-encoded binary (envelope + payload) using the schema
registry module. Consumes in a background asyncio task per subscription,
polling Kafka in a thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from app.shared.events import BaseEvent, EventHandler
from app.shared.schema_registry import deserialize_event, serialize_event

if TYPE_CHECKING:
    from confluent_kafka import Message

logger = structlog.get_logger()


class KafkaEventBus:
    """Kafka-backed event bus implementing the ``EventBus`` protocol.

    - **Publishing** is async: ``confluent_kafka.Producer.produce()`` is
      non-blocking; delivery confirmation is polled in a background task.
    - **Subscribing** spawns a background asyncio task per topic that polls
      Kafka in a thread pool to avoid blocking the event loop.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        *,
        consumer_group: str = "minihedge",
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group

        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "linger.ms": 5,
                "compression.type": "snappy",
            }
        )

        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._consumers: list[Consumer] = []
        self._consumer_tasks: list[asyncio.Task[None]] = []
        self._running = False
        self._dlq_max_retries = 3
        self._failure_counts: dict[str, int] = {}
        self._dlq_count = 0

    async def publish(self, topic: str, event: BaseEvent) -> None:
        """Serialize and produce an event to a Kafka topic."""
        envelope = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "event_version": event.event_version,
            "timestamp": event.timestamp.isoformat(),
            "actor_id": event.actor_id,
            "actor_type": event.actor_type,
            "fund_slug": event.fund_slug,
        }
        payload = event.data

        try:
            value = serialize_event(topic, envelope, payload)
        except (ValueError, RuntimeError):
            logger.exception("event_serialization_failed", topic=topic, event_id=event.event_id)
            return

        # Partition key: use instrument_id or portfolio_id for ordering
        key = event.data.get("instrument_id") or event.data.get("portfolio_id") or event.event_id

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._producer.produce,
                topic=topic,
                value=value,
                key=key.encode(),
            ),
        )
        # Flush periodically — the producer batches internally
        self._producer.poll(0)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register a handler for a topic.

        Handlers are collected before ``start()`` is called.  When ``start()``
        runs, one consumer task is created per unique topic.
        """
        self._handlers[topic].append(handler)

    async def start(self) -> None:
        """Start background consumer tasks for all subscribed topics."""
        self._running = True
        for topic, handlers in self._handlers.items():
            consumer = Consumer(
                {
                    "bootstrap.servers": self._bootstrap_servers,
                    "group.id": f"{self._consumer_group}-{topic}",
                    "auto.offset.reset": "latest",
                    "enable.auto.commit": False,
                }
            )
            consumer.subscribe([topic])
            self._consumers.append(consumer)

            task = asyncio.create_task(
                self._consume_loop(topic, consumer, handlers),
                name=f"kafka-consumer-{topic}",
            )
            self._consumer_tasks.append(task)

        logger.info(
            "kafka_consumers_started",
            topics=list(self._handlers.keys()),
        )

    async def _consume_loop(
        self,
        topic: str,
        consumer: Consumer,
        handlers: list[EventHandler],
    ) -> None:
        """Poll Kafka in a thread, dispatch to handlers on the event loop."""
        loop = asyncio.get_running_loop()

        while self._running:
            try:
                msg: Message | None = await loop.run_in_executor(
                    None,
                    partial(consumer.poll, 1.0),
                )
            except KafkaException:
                logger.exception("kafka_poll_error", topic=topic)
                await asyncio.sleep(1)
                continue

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("kafka_message_error", topic=topic, error=str(msg.error()))
                continue

            try:
                envelope, payload = deserialize_event(topic, msg.value())
                event = BaseEvent(
                    event_id=envelope["event_id"],
                    event_type=envelope["event_type"],
                    event_version=envelope.get("event_version", 1),
                    timestamp=datetime.fromisoformat(envelope["timestamp"]),
                    data=payload,
                    actor_id=envelope.get("actor_id"),
                    actor_type=envelope.get("actor_type"),
                    fund_slug=envelope.get("fund_slug"),
                )
            except Exception:
                logger.exception("event_deserialization_failed", topic=topic)
                continue

            all_ok = True
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    all_ok = False
                    logger.exception(
                        "kafka_handler_failed",
                        topic=topic,
                        handler=getattr(handler, "__qualname__", str(handler)),
                        event_id=event.event_id,
                    )

            if all_ok:
                self._failure_counts.pop(event.event_id, None)
                await loop.run_in_executor(None, consumer.commit)
            else:
                count = self._failure_counts.get(event.event_id, 0) + 1
                self._failure_counts[event.event_id] = count
                if count >= self._dlq_max_retries:
                    self._publish_to_dlq(topic, event, msg.value())
                    self._failure_counts.pop(event.event_id, None)
                    await loop.run_in_executor(None, consumer.commit)
                else:
                    logger.warning(
                        "kafka_commit_skipped",
                        topic=topic,
                        event_id=event.event_id,
                        failure_count=count,
                    )

    @property
    def dlq_count(self) -> int:
        """Number of events sent to dead-letter queues."""
        return self._dlq_count

    def _publish_to_dlq(self, topic: str, event: BaseEvent, raw_value: bytes) -> None:
        """Publish a failed event to the dead-letter queue topic."""
        dlq_topic = f"{topic}.dlq"
        try:
            self._producer.produce(
                topic=dlq_topic,
                value=raw_value,
                key=event.event_id.encode(),
            )
            self._producer.poll(0)
            self._dlq_count += 1
            logger.error(
                "event_sent_to_dlq",
                topic=topic,
                dlq_topic=dlq_topic,
                event_id=event.event_id,
            )
        except Exception:
            logger.exception(
                "dlq_publish_failed",
                topic=topic,
                event_id=event.event_id,
            )

    def health_check(self) -> bool:
        """Check if the Kafka producer is healthy."""
        try:
            self._producer.flush(timeout=2.0)
            return True
        except Exception:
            return False

    async def stop(self) -> None:
        """Stop all consumer tasks and flush the producer."""
        self._running = False

        for task in self._consumer_tasks:
            task.cancel()

        for task in self._consumer_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        for consumer in self._consumers:
            consumer.close()

        # Flush remaining produce messages
        self._producer.flush(timeout=5.0)

        self._consumer_tasks.clear()
        self._consumers.clear()

        logger.info("kafka_event_bus_stopped")

    def ensure_topics(self, topics: list[str], num_partitions: int = 3) -> None:
        """Create Kafka topics if they don't exist.

        Called during startup to ensure all required topics are available.
        """
        admin = AdminClient({"bootstrap.servers": self._bootstrap_servers})
        new_topics = [
            NewTopic(topic, num_partitions=num_partitions, replication_factor=1) for topic in topics
        ]
        futures = admin.create_topics(new_topics)
        for topic, future in futures.items():
            try:
                future.result()
                logger.info("kafka_topic_created", topic=topic)
            except KafkaException as e:
                # TOPIC_ALREADY_EXISTS is fine
                if "TOPIC_ALREADY_EXISTS" in str(e):
                    logger.debug("kafka_topic_exists", topic=topic)
                else:
                    logger.error("kafka_topic_create_failed", topic=topic, error=str(e))
