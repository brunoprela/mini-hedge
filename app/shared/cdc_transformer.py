"""CDC-to-domain-event transformer.

Consumes Debezium change events from ``cdc.*`` Kafka topics and re-publishes
them as domain events on the existing internal Kafka topics. This replaces
application-level dual-writes: services write to their domain tables and
Debezium captures every committed change from the PostgreSQL WAL.

The transformer maps CDC table changes to domain event types::

    cdc.fund_alpha.current_positions  →  fund-alpha.positions.changed
    cdc.fund_alpha.orders             →  fund-alpha.orders.created  (on insert)
    cdc.fund_alpha.orders             →  fund-alpha.orders.filled   (on status→filled)
    cdc.fund_alpha.compliance_violations → fund-alpha.compliance.violations

Downstream consumers (risk, exposure, compliance, cash, audit) are unchanged —
they continue consuming from the same domain topics.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logger = structlog.get_logger()

# Regex to extract schema and table from a CDC topic name.
# Debezium topic format: cdc.{schema}.{table}
_CDC_TOPIC_PATTERN = re.compile(r"^cdc\.(?P<schema>[^.]+)\.(?P<table>.+)$")

# Regex to extract fund slug from a fund schema name.
# Schema format: fund_{slug} where slug may contain underscores.
_FUND_SCHEMA_PATTERN = re.compile(r"^fund_(.+)$")


def _schema_to_fund_slug(schema: str) -> str | None:
    """Extract fund slug from a PostgreSQL schema name.

    ``fund_alpha`` → ``fund-alpha``
    ``platform`` → None (not a fund schema)
    """
    match = _FUND_SCHEMA_PATTERN.match(schema)
    if match is None:
        return None
    # Reverse the slug sanitization: underscores back to hyphens
    return match.group(1).replace("_", "-")


def _map_cdc_to_domain_event(
    schema: str,
    table: str,
    operation: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any]] | None:
    """Map a CDC change to (domain_topic_suffix, event_type, payload).

    Returns None if the change should not be forwarded as a domain event.
    """
    if table == "current_positions" and operation in ("c", "u", "r"):
        row = after or {}
        return (
            "positions.changed",
            "position.changed",
            {
                "instrument_id": row.get("instrument_id", ""),
                "portfolio_id": row.get("portfolio_id", ""),
                "quantity": str(row.get("quantity", "0")),
                "market_value": str(row.get("market_value", "0")),
                "market_price": str(row.get("market_price", "0")),
                "avg_cost": str(row.get("avg_cost", "0")),
                "unrealized_pnl": str(row.get("unrealized_pnl", "0")),
                "cdc_operation": operation,
            },
        )

    if table == "orders":
        row = after or {}
        status = row.get("status", "")

        if operation == "c":
            return (
                "orders.created",
                "order.created",
                {
                    "order_id": row.get("id", ""),
                    "portfolio_id": row.get("portfolio_id", ""),
                    "instrument_id": row.get("instrument_id", ""),
                    "side": row.get("side", ""),
                    "quantity": str(row.get("quantity", "0")),
                    "status": status,
                    "cdc_operation": operation,
                },
            )

        if operation == "u" and status == "filled":
            return (
                "orders.filled",
                "order.filled",
                {
                    "order_id": row.get("id", ""),
                    "portfolio_id": row.get("portfolio_id", ""),
                    "instrument_id": row.get("instrument_id", ""),
                    "side": row.get("side", ""),
                    "quantity": str(row.get("quantity", "0")),
                    "fill_price": str(row.get("fill_price", "0")),
                    "status": status,
                    "cdc_operation": operation,
                },
            )

    if table == "compliance_violations" and operation in ("c", "u", "r"):
        row = after or {}
        return (
            "compliance.violations",
            "compliance.violation",
            {
                "violation_id": row.get("id", ""),
                "portfolio_id": row.get("portfolio_id", ""),
                "rule_id": row.get("rule_id", ""),
                "rule_name": row.get("rule_name", ""),
                "severity": row.get("severity", ""),
                "message": row.get("message", ""),
                "cdc_operation": operation,
            },
        )

    if table == "risk_snapshots" and operation in ("c", "r"):
        row = after or {}
        return (
            "risk.updated",
            "risk.updated",
            {
                "portfolio_id": row.get("portfolio_id", ""),
                "nav": str(row.get("nav", "0")),
                "var_95_1d": str(row.get("var_95_1d", "0")),
                "var_99_1d": str(row.get("var_99_1d", "0")),
                "cdc_operation": operation,
            },
        )

    if table == "exposure_snapshots" and operation in ("c", "r"):
        row = after or {}
        return (
            "exposures.updated",
            "exposure.updated",
            {
                "portfolio_id": row.get("portfolio_id", ""),
                "cdc_operation": operation,
            },
        )

    if table in ("cash_entries", "settlement_entries") and operation in ("c", "u", "r"):
        row = after or {}
        return (
            "cash.settlement.created",
            "cash.settlement",
            {
                "portfolio_id": row.get("portfolio_id", ""),
                "amount": str(row.get("amount", "0")),
                "currency": row.get("currency", "USD"),
                "cdc_operation": operation,
            },
        )

    # Unrecognized table or operation — skip
    return None


class CdcTransformer:
    """Consumes Debezium CDC events and re-publishes as domain events.

    Runs as a set of background tasks, one per CDC topic pattern.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        consumer_group: str = "minihedge-cdc-transformer",
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._events_transformed = 0
        self._events_skipped = 0

    @property
    def events_transformed(self) -> int:
        return self._events_transformed

    @property
    def events_skipped(self) -> int:
        return self._events_skipped

    async def start(self, cdc_topic_pattern: str = "^cdc\\.fund_.*") -> None:
        """Start consuming CDC topics matching the given regex pattern."""
        self._running = True

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            acks="all",
            enable_idempotence=True,
            linger_ms=5,
            compression_type="snappy",
        )
        await asyncio.wait_for(self._producer.start(), timeout=30)

        self._consumer = AIOKafkaConsumer(
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self._consumer.subscribe(pattern=cdc_topic_pattern)
        await asyncio.wait_for(self._consumer.start(), timeout=30)

        self._task = asyncio.create_task(
            self._consume_loop(),
            name="cdc-transformer",
        )
        logger.info(
            "cdc_transformer_started",
            pattern=cdc_topic_pattern,
            group=self._consumer_group,
        )

    async def _consume_loop(self) -> None:
        """Main consume loop — reads CDC events and publishes domain events."""
        assert self._consumer is not None
        assert self._producer is not None

        while self._running:
            try:
                msg_batch = await self._consumer.getmany(timeout_ms=1000, max_records=50)
            except Exception:
                logger.exception("cdc_transformer_poll_error")
                await asyncio.sleep(1)
                continue

            for _tp, messages in msg_batch.items():
                for msg in messages:
                    if msg.value is None:
                        continue
                    await self._process_message(msg.topic, msg.value)

            if msg_batch:
                try:
                    await self._consumer.commit()
                except Exception:
                    logger.exception("cdc_transformer_commit_error")

    async def _process_message(self, topic: str, raw_value: bytes) -> None:
        """Process a single CDC message."""
        match = _CDC_TOPIC_PATTERN.match(topic)
        if match is None:
            self._events_skipped += 1
            return

        schema = match.group("schema")
        table = match.group("table")
        fund_slug = _schema_to_fund_slug(schema)

        if fund_slug is None:
            # Platform or eod schema — not yet mapped to domain events
            self._events_skipped += 1
            return

        try:
            # Debezium publishes JSON or Avro. For now, handle JSON
            # (the connector config can use JSON converters for simplicity,
            # or Avro — the deserializer will handle both via config).
            event = json.loads(raw_value)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("cdc_transformer_decode_error", topic=topic)
            self._events_skipped += 1
            return

        # Debezium envelope: {"before": ..., "after": ..., "op": "c/u/d/r", "source": ...}
        operation = event.get("op")
        before = event.get("before")
        after = event.get("after")

        if operation is None:
            self._events_skipped += 1
            return

        result = _map_cdc_to_domain_event(schema, table, operation, before, after)
        if result is None:
            self._events_skipped += 1
            return

        topic_suffix, event_type, payload = result
        domain_topic = f"fund-{fund_slug}.{topic_suffix}"

        # Publish as a simple JSON domain event on the internal topic
        domain_event = {
            "event_type": event_type,
            "data": payload,
            "fund_slug": fund_slug,
            "source": "cdc",
        }

        assert self._producer is not None
        try:
            key = (
                payload.get("instrument_id")
                or payload.get("portfolio_id")
                or payload.get("order_id")
                or ""
            )
            await self._producer.send(
                topic=domain_topic,
                value=json.dumps(domain_event).encode(),
                key=key.encode() if key else None,
            )
            self._events_transformed += 1
            logger.debug(
                "cdc_event_transformed",
                cdc_topic=topic,
                domain_topic=domain_topic,
                event_type=event_type,
                operation=operation,
            )
        except Exception:
            logger.exception(
                "cdc_transform_publish_failed",
                domain_topic=domain_topic,
                event_type=event_type,
            )

    async def stop(self) -> None:
        """Stop the transformer gracefully."""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

        logger.info(
            "cdc_transformer_stopped",
            events_transformed=self._events_transformed,
            events_skipped=self._events_skipped,
        )
