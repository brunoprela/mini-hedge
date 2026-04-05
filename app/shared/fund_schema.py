"""Per-fund schema lifecycle management.

Creates and migrates PostgreSQL schemas for each fund.  Position data is
isolated by schema: ``fund_{slug}.events``, ``fund_{slug}.current_positions``.

Alembic migrations for the ``positions`` module are re-used — the migration
env.py accepts a ``target_schema`` override via Alembic's ``x`` argument.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text

from app.shared.schema_registry import fund_topics_for_slug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger()

# Schema name prefix for fund schemas.
FUND_SCHEMA_PREFIX = "fund_"


def fund_schema_name(fund_slug: str) -> str:
    """Derive the PostgreSQL schema name from a fund slug.

    Hyphens are replaced with underscores to produce a valid unquoted
    PostgreSQL identifier: ``fund-alpha`` → ``fund_alpha``.
    """
    sanitized = fund_slug.replace("-", "_")
    return f"{FUND_SCHEMA_PREFIX}{sanitized}"


async def create_fund_schema(engine: AsyncEngine, fund_slug: str) -> None:
    """Create a fund schema and run positions migrations against it.

    Safe to call multiple times — ``CREATE SCHEMA IF NOT EXISTS`` and
    Alembic's version table prevent duplicate work.
    """
    schema = fund_schema_name(fund_slug)
    lock_id = hash(fund_slug) & 0x7FFFFFFF
    async with engine.begin() as conn:
        await conn.execute(text(f"SELECT pg_advisory_lock({lock_id})"))
        try:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        finally:
            await conn.execute(text(f"SELECT pg_advisory_unlock({lock_id})"))
    logger.info("fund_schema_ensured", fund_slug=fund_slug, schema=schema)
    await asyncio.to_thread(_run_fund_migrations_sync, fund_slug)
    logger.info("fund_migrations_applied", fund_slug=fund_slug, schema=schema)


# Modules that store data in per-fund schemas.
_FUND_SCOPED_MODULES = [
    "positions",
    "exposure",
    "compliance",
    "orders",
    "risk_engine",
    "cash_management",
    "attribution",
    "alpha_engine",
]


def _run_fund_migrations_sync(fund_slug: str) -> None:
    """Run per-fund-schema Alembic migrations for all fund-scoped modules.

    Each module's env.py uses ``schema_translate_map`` to remap the
    default ``positions`` schema to ``fund_{slug}``.
    """
    schema = fund_schema_name(fund_slug)
    for module in _FUND_SCOPED_MODULES:
        cfg = AlembicConfig("alembic.ini", ini_section=module)
        cfg.set_section_option(
            module,
            "script_location",
            f"app/modules/{module}/migrations",
        )
        cfg.attributes["target_schema"] = schema
        alembic_command.upgrade(cfg, "head")


def create_fund_kafka_topics(
    kafka_bus: object,
    fund_slug: str,
) -> None:
    """Create Kafka topics for a newly onboarded fund.

    Accepts any object with an ``ensure_topics`` method (i.e. ``KafkaEventBus``)
    so this module doesn't depend on the Kafka implementation.
    """
    topics = fund_topics_for_slug(fund_slug)
    kafka_bus.ensure_topics(topics)  # type: ignore[attr-defined]
    logger.info("fund_kafka_topics_created", fund_slug=fund_slug, topics=topics)


async def ensure_all_fund_schemas(engine: AsyncEngine, fund_slugs: list[str]) -> None:
    """Ensure schemas and migrations exist for all active funds.

    Called during application startup.
    """
    for slug in fund_slugs:
        await create_fund_schema(engine, slug)
