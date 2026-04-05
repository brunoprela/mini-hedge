"""CDC audit enrichment consumer.

Consumes raw Debezium CDC events from ``cdc.*`` topics and persists
before/after row snapshots to the audit log.  This gives compliance
teams row-level change visibility — who changed what, from what value,
to what value — captured directly from the PostgreSQL WAL.

Unlike the :mod:`~app.shared.cdc_transformer` (which maps CDC to domain
events), this consumer captures the raw change for audit purposes.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING, Any

import structlog
from aiokafka import AIOKafkaConsumer

if TYPE_CHECKING:
    from app.modules.platform.audit_repository import AuditLogRepository

logger = structlog.get_logger()

# Debezium op codes
_OP_NAMES = {
    "c": "INSERT",
    "u": "UPDATE",
    "d": "DELETE",
    "r": "SNAPSHOT",
}


class CdcAuditConsumer:
    """Persists CDC row-level changes to the audit log for compliance.

    Runs as a background asyncio task consuming from all ``cdc.*`` topics.
    Each CDC event is stored with before/after snapshots so auditors can
    see exactly what changed at the database level.
    """

    def __init__(
        self,
        *,
        audit_repo: AuditLogRepository,
        bootstrap_servers: str,
        consumer_group: str = "minihedge-cdc-audit",
    ) -> None:
        self._audit_repo = audit_repo
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._events_persisted = 0

    @property
    def events_persisted(self) -> int:
        return self._events_persisted

    async def start(self, topic_pattern: str = "^cdc\\.fund_.*") -> None:
        """Start consuming CDC topics and persisting to audit log."""
        self._running = True

        self._consumer = AIOKafkaConsumer(
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self._consumer.subscribe(pattern=topic_pattern)
        await asyncio.wait_for(self._consumer.start(), timeout=30)

        self._task = asyncio.create_task(
            self._consume_loop(),
            name="cdc-audit-consumer",
        )
        logger.info(
            "cdc_audit_consumer_started",
            pattern=topic_pattern,
            group=self._consumer_group,
        )

    async def _consume_loop(self) -> None:
        assert self._consumer is not None

        while self._running:
            try:
                msg_batch = await self._consumer.getmany(timeout_ms=1000, max_records=50)
            except Exception:
                logger.exception("cdc_audit_poll_error")
                await asyncio.sleep(1)
                continue

            for _tp, messages in msg_batch.items():
                for msg in messages:
                    if msg.value is None:
                        continue
                    await self._persist_change(msg.topic, msg.value)

            if msg_batch:
                try:
                    await self._consumer.commit()
                except Exception:
                    logger.exception("cdc_audit_commit_error")

    async def _persist_change(self, topic: str, raw_value: bytes) -> None:
        """Parse a CDC event and write an audit record with before/after snapshots."""
        try:
            event = json.loads(raw_value)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        operation = event.get("op")
        if operation is None:
            return

        source: dict[str, Any] = event.get("source", {})
        schema = source.get("schema", "")
        table = source.get("table", "")

        # Derive fund slug from schema name (fund_alpha → fund-alpha)
        fund_slug: str | None = None
        if schema.startswith("fund_"):
            fund_slug = schema[5:].replace("_", "-")

        before = event.get("before")
        after = event.get("after")

        # Build a stable event_id from the CDC source offset to ensure idempotency
        lsn = source.get("lsn", "")
        event_id = f"cdc-{schema}-{table}-{lsn}-{operation}"

        payload: dict[str, Any] = {
            "cdc_operation": _OP_NAMES.get(operation, operation),
            "schema": schema,
            "table": table,
            "cdc_topic": topic,
        }
        if before is not None:
            payload["before"] = _sanitize_row(before)
        if after is not None:
            payload["after"] = _sanitize_row(after)

        # Compute a human-readable diff for UPDATE operations
        if operation == "u" and before and after:
            payload["changes"] = _compute_diff(before, after)

        try:
            await self._audit_repo.insert_admin_event(
                event_type=f"cdc.{table}.{_OP_NAMES.get(operation, operation).lower()}",
                actor_id="debezium",
                actor_type="system",
                fund_slug=fund_slug,
                payload=payload,
            )
            self._events_persisted += 1
        except Exception:
            logger.exception(
                "cdc_audit_persist_failed",
                topic=topic,
                event_id=event_id,
            )

    async def stop(self) -> None:
        """Stop the consumer gracefully."""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

        logger.info(
            "cdc_audit_consumer_stopped",
            events_persisted=self._events_persisted,
        )


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert row values to JSON-safe strings (handles Decimal, bytes, etc.)."""
    return {k: str(v) if v is not None else None for k, v in row.items()}


def _compute_diff(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, dict[str, str | None]]:
    """Return only the fields that changed between before and after."""
    diff: dict[str, dict[str, str | None]] = {}
    for key in set(before) | set(after):
        old_val = before.get(key)
        new_val = after.get(key)
        if old_val != new_val:
            diff[key] = {
                "from": str(old_val) if old_val is not None else None,
                "to": str(new_val) if new_val is not None else None,
            }
    return diff
