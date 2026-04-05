"""Kafka event bus — production ``EventBus`` implementation over aiokafka.

Produces Avro-encoded events (envelope + payload) via the schema registry.
Consumes in native async tasks — no thread pool needed.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from datetime import datetime
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import KafkaError, TopicAlreadyExistsError

from app.shared.events import BaseEvent, EventHandler
from app.shared.schema_registry import deserialize_event, serialize_event

logger = structlog.get_logger()


class KafkaEventBus:
    """Production event bus backed by aiokafka.

    Publishing is non-blocking (native async ``send``).  Each subscribed
    topic gets a background consumer task — fully async, no thread pool.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        *,
        consumer_group: str = "minihedge",
        replication_factor: int = 1,
        num_partitions: int = 3,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._replication_factor = replication_factor
        self._num_partitions = num_partitions

        self._producer: AIOKafkaProducer | None = None

        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._consumers: list[AIOKafkaConsumer] = []
        self._consumer_tasks: list[asyncio.Task[None]] = []
        self._running = False
        self._dlq_max_retries = 3
        self._failure_counts: dict[str, int] = {}
        self._dlq_count = 0

    async def _get_producer(self) -> AIOKafkaProducer:
        """Lazily start the producer on first use."""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                linger_ms=5,
                compression_type="snappy",
                acks="all",
                enable_idempotence=True,
                max_request_size=1048576,
                request_timeout_ms=10000,
            )
            await self._producer.start()
        return self._producer

    async def publish(self, topic: str, event: BaseEvent) -> None:
        """Serialize and produce an event to a Kafka topic."""
        envelope: dict[str, Any] = {
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

        producer = await self._get_producer()
        try:
            await producer.send(
                topic=topic,
                value=value,
                key=key.encode(),
            )
        except KafkaError:
            logger.exception("kafka_produce_failed", topic=topic, event_id=event.event_id)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register a handler for a topic.

        Handlers are collected before ``start()`` is called.  When ``start()``
        runs, one consumer task is created per unique topic.
        """
        self._handlers[topic].append(handler)

    async def start(self) -> None:
        """Start background consumer tasks for all subscribed topics."""
        self._running = True

        # Ensure producer is ready
        await self._get_producer()

        for topic, handlers in self._handlers.items():
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self._bootstrap_servers,
                group_id=f"{self._consumer_group}-{topic}",
                auto_offset_reset="latest",
                enable_auto_commit=False,
                session_timeout_ms=10000,
                heartbeat_interval_ms=3000,
                max_poll_interval_ms=60000,
                fetch_max_wait_ms=100,
            )
            await consumer.start()
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
        consumer: AIOKafkaConsumer,
        handlers: list[EventHandler],
    ) -> None:
        """Async consume from Kafka, dispatch to handlers."""
        while self._running:
            try:
                msg_batch = await consumer.getmany(timeout_ms=1000, max_records=10)
            except KafkaError:
                logger.exception("kafka_poll_error", topic=topic)
                await asyncio.sleep(1)
                continue

            for _tp, messages in msg_batch.items():
                for msg in messages:
                    if msg.value is None:
                        continue

                    try:
                        envelope, payload = deserialize_event(topic, msg.value)
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
                    else:
                        count = self._failure_counts.get(event.event_id, 0) + 1
                        self._failure_counts[event.event_id] = count
                        if count >= self._dlq_max_retries:
                            # Always commit after max retries to avoid infinite loop,
                            # even if DLQ publish fails.
                            await self._publish_to_dlq(topic, event, msg.value)
                            self._failure_counts.pop(event.event_id, None)
                        else:
                            logger.warning(
                                "kafka_handler_retry_pending",
                                topic=topic,
                                event_id=event.event_id,
                                failure_count=count,
                                max_retries=self._dlq_max_retries,
                            )

            # Always commit the batch — failed messages beyond retry limit
            # are sent to DLQ and must be committed to avoid reprocessing.
            try:
                await consumer.commit()
            except KafkaError:
                logger.exception("kafka_commit_failed", topic=topic)

    @property
    def dlq_count(self) -> int:
        """Number of events sent to dead-letter queues."""
        return self._dlq_count

    async def _publish_to_dlq(self, topic: str, event: BaseEvent, raw_value: bytes) -> None:
        """Publish a failed event to the dead-letter queue topic."""
        dlq_topic = f"{topic}.dlq"
        try:
            producer = await self._get_producer()
            await producer.send(
                topic=dlq_topic,
                value=raw_value,
                key=event.event_id.encode(),
            )
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

    async def health_check(self) -> bool:
        """Check producer connectivity and consumer liveness."""
        try:
            if self._producer is None:
                return False
            # Partitions call confirms broker connectivity
            await self._producer.partitions_for("__consumer_offsets")
        except Exception:
            return False

        # Verify consumer tasks are still running
        for task in self._consumer_tasks:
            if task.done() and not task.cancelled():
                exc = task.exception()
                if exc is not None:
                    logger.error("kafka_consumer_task_dead", error=str(exc))
                    return False

        return True

    async def stop(self, drain_timeout: float = 5.0) -> None:
        """Gracefully stop all consumer tasks and flush the producer.

        Sets ``_running = False`` and waits up to ``drain_timeout`` seconds
        for in-flight handlers to complete before cancelling tasks. This
        prevents interrupting handlers mid-execution.
        """
        self._running = False

        # Wait for current poll cycles to finish (they check _running)
        if self._consumer_tasks:
            _, pending = await asyncio.wait(self._consumer_tasks, timeout=drain_timeout)
            # Cancel any tasks that didn't finish within the drain period
            for task in pending:
                task.cancel()
            for task in pending:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        for consumer in self._consumers:
            await consumer.stop()

        # Flush producer after consumers — handlers may publish during drain
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

        self._consumer_tasks.clear()
        self._consumers.clear()

        logger.info("kafka_event_bus_stopped")

    async def ensure_topics(self, topics: list[str]) -> None:
        """Create Kafka topics if they don't exist.

        Called during startup to ensure all required topics are available.
        Uses the replication_factor and num_partitions from constructor config.
        """
        admin = AIOKafkaAdminClient(bootstrap_servers=self._bootstrap_servers)
        await admin.start()
        try:
            new_topics = [
                NewTopic(
                    name=topic,
                    num_partitions=self._num_partitions,
                    replication_factor=self._replication_factor,
                )
                for topic in topics
            ]
            try:
                await admin.create_topics(new_topics)
                logger.info("kafka_topics_ensured", count=len(topics))
            except TopicAlreadyExistsError:
                logger.debug("kafka_topics_already_exist")
        finally:
            await admin.close()
