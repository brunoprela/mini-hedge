"""Avro schema management — loads .avsc files, serializes/deserializes events.

Uses ``fastavro`` for Avro encoding and Confluent Schema Registry's REST API
(via ``confluent_kafka.schema_registry``) for schema registration and lookup.
The envelope/payload pattern separates event metadata from domain data so each
can evolve independently.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import fastavro
import structlog
from confluent_kafka.schema_registry import Schema, SchemaRegistryClient

logger = structlog.get_logger()

# Directory containing .avsc files, relative to project root.
_SCHEMA_DIR = Path("schemas")

# Topic prefixes for fund-scoped and shared topics.
_FUND_TOPIC_PREFIX = "fund-"
_SHARED_TOPIC_PREFIX = "shared."


def shared_topic(base: str) -> str:
    """Build a shared (global) topic name: ``shared.prices.normalized``."""
    return f"{_SHARED_TOPIC_PREFIX}{base}"


def fund_topic(fund_slug: str, base: str) -> str:
    """Build a fund-scoped topic name: ``fund-alpha.positions.changed``."""
    return f"{_FUND_TOPIC_PREFIX}{fund_slug}.{base}"


def base_topic_name(topic: str) -> str:
    """Strip the ``shared.`` or ``fund-{slug}.`` prefix to get the base topic.

    Used to look up the Avro schema regardless of whether the event
    was published to a fund-scoped or shared topic.

    >>> base_topic_name("shared.prices.normalized")
    'prices.normalized'
    >>> base_topic_name("fund-alpha.positions.changed")
    'positions.changed'
    >>> base_topic_name("prices.normalized")
    'prices.normalized'
    """
    if topic.startswith(_SHARED_TOPIC_PREFIX):
        return topic[len(_SHARED_TOPIC_PREFIX) :]

    if topic.startswith(_FUND_TOPIC_PREFIX):
        # fund-{slug}.{base} — strip everything up to and including the first dot after the slug
        first_dot = topic.index(".", len(_FUND_TOPIC_PREFIX))
        return topic[first_dot + 1 :]

    return topic


def fund_topics_for_slug(fund_slug: str) -> list[str]:
    """Return all fund-scoped Kafka topics for a given fund slug."""
    return [
        fund_topic(fund_slug, "positions.changed"),
        fund_topic(fund_slug, "pnl.updated"),
        fund_topic(fund_slug, "trades.executed"),
        fund_topic(fund_slug, "exposures.updated"),
        fund_topic(fund_slug, "compliance.violations"),
        fund_topic(fund_slug, "orders.created"),
        fund_topic(fund_slug, "orders.filled"),
        fund_topic(fund_slug, "trades.approved"),
        fund_topic(fund_slug, "trades.rejected"),
        fund_topic(fund_slug, "risk.updated"),
        fund_topic(fund_slug, "cash.settlement.created"),
        fund_topic(fund_slug, "cash.settlement.settled"),
    ]


def shared_topics() -> list[str]:
    """Return all shared (global) Kafka topics."""
    return [
        shared_topic("prices.normalized"),
    ]


# Maps event_type → Avro parsed schema for the *payload* (data field).
# Keyed by event_type (not topic) because a single topic can carry multiple
# event types with different payload schemas (e.g. pnl.updated carries both
# pnl.realized and pnl.mark_to_market events).
_PAYLOAD_SCHEMAS: dict[str, dict[str, Any]] = {}

# Envelope schema (wraps every event on Kafka).
_ENVELOPE_SCHEMA: dict[str, Any] | None = None


def _load_avsc(path: Path) -> dict[str, Any]:
    """Load and parse an Avro schema from a .avsc JSON file."""
    with path.open() as f:
        return json.load(f)


def load_schemas() -> None:
    """Load all Avro schemas from disk into module-level caches.

    Called once at startup. Maps event types to their payload schemas.
    """
    global _ENVELOPE_SCHEMA  # noqa: PLW0603

    _ENVELOPE_SCHEMA = _load_avsc(_SCHEMA_DIR / "envelope-v1.avsc")
    fastavro.parse_schema(_ENVELOPE_SCHEMA)

    # event_type → schema file mapping
    event_schemas = {
        "price.updated": "prices/normalized-v1.avsc",
        "position.changed": "positions/changed-v1.avsc",
        "pnl.realized": "positions/pnl-realized-v1.avsc",
        "pnl.mark_to_market": "positions/pnl-mtm-v1.avsc",
        "trade.buy": "trades/executed-v1.avsc",
        "trade.sell": "trades/executed-v1.avsc",
        "trade.approved": "trades/executed-v1.avsc",
        "trade.rejected": "trades/executed-v1.avsc",
        "order.created": "orders/created-v1.avsc",
        "order.filled": "orders/filled-v1.avsc",
        "compliance.violation": "compliance/violation-v1.avsc",
        "compliance.violation.resolved": "compliance/violation-v1.avsc",
        "exposure.updated": "exposure/updated-v1.avsc",
        "risk.updated": "risk/updated-v1.avsc",
        "cash.settlement.created": "cash/settlement-v1.avsc",
        "cash.settlement.settled": "cash/settlement-v1.avsc",
    }
    for event_type, schema_file in event_schemas.items():
        schema = _load_avsc(_SCHEMA_DIR / schema_file)
        fastavro.parse_schema(schema)
        _PAYLOAD_SCHEMAS[event_type] = schema

    logger.info("avro_schemas_loaded", event_types=list(_PAYLOAD_SCHEMAS.keys()))


def _avro_encode(schema: dict[str, Any], record: dict[str, Any]) -> bytes:
    """Encode a record to Avro binary using fastavro."""
    buf = io.BytesIO()
    fastavro.schemaless_writer(buf, schema, record)
    return buf.getvalue()


def _avro_decode(schema: dict[str, Any], data: bytes) -> dict[str, Any]:
    """Decode Avro binary back to a dict using fastavro."""
    buf = io.BytesIO(data)
    return fastavro.schemaless_reader(buf, schema)


def serialize_event(
    topic: str,
    envelope: dict[str, Any],
    payload: dict[str, Any],
) -> bytes:
    """Serialize an event envelope + payload to Avro binary.

    The payload is first encoded with its event-type-specific schema, then
    embedded as ``bytes`` in the envelope's ``data`` field.
    """
    event_type = envelope.get("event_type", "")
    payload_schema = _PAYLOAD_SCHEMAS.get(event_type)
    if payload_schema is None:
        raise ValueError(f"No Avro schema registered for event_type: {event_type} (topic: {topic})")

    if _ENVELOPE_SCHEMA is None:
        raise RuntimeError("Schemas not loaded — call load_schemas() at startup")

    encoded_payload = _avro_encode(payload_schema, payload)

    envelope_record = {
        **envelope,
        "data": encoded_payload,
    }
    return _avro_encode(_ENVELOPE_SCHEMA, envelope_record)


def deserialize_event(
    topic: str,
    raw: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Deserialize Avro binary back to (envelope, payload) dicts.

    Decodes the envelope first to extract ``event_type``, then uses the
    event-type-specific schema to decode the payload.
    """
    if _ENVELOPE_SCHEMA is None:
        raise RuntimeError("Schemas not loaded — call load_schemas() at startup")

    envelope = _avro_decode(_ENVELOPE_SCHEMA, raw)

    event_type = envelope.get("event_type", "")
    payload_schema = _PAYLOAD_SCHEMAS.get(event_type)
    if payload_schema is None:
        raise ValueError(f"No Avro schema registered for event_type: {event_type} (topic: {topic})")

    payload = _avro_decode(payload_schema, envelope["data"])
    envelope["data"] = payload
    return envelope, payload


def register_schemas(registry_url: str) -> None:
    """Register all Avro schemas with Confluent Schema Registry.

    Uses BACKWARD compatibility (Confluent default). Subject naming
    follows ``{topic}-value`` convention.
    """
    client = SchemaRegistryClient({"url": registry_url})

    # Register envelope schema
    if _ENVELOPE_SCHEMA is not None:
        envelope_schema = Schema(
            json.dumps(_ENVELOPE_SCHEMA),
            schema_type="AVRO",
        )
        schema_id = client.register_schema("event-envelope-value", envelope_schema)
        logger.info("schema_registered", subject="event-envelope-value", schema_id=schema_id)

    # Register payload schemas
    for topic, schema in _PAYLOAD_SCHEMAS.items():
        avro_schema = Schema(json.dumps(schema), schema_type="AVRO")
        subject = f"{topic}-value"
        schema_id = client.register_schema(subject, avro_schema)
        logger.info("schema_registered", subject=subject, schema_id=schema_id)
