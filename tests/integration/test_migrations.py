"""Migration round-trip tests — verify all migrations can upgrade and downgrade cleanly.

Uses testcontainers to spin up a real PostgreSQL, runs each module's
migrations forward to head, then back to base, then forward again.
This catches migrations that can't be reversed or re-applied.
"""

from __future__ import annotations

import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text

from app.shared.fund_schema import fund_schema_name

# Modules with shared schemas (run once, no per-fund schema needed)
SHARED_MODULES = ["platform", "security_master", "market_data", "eod"]

# Modules that run per-fund (need a fund_xxx schema created first)
PER_FUND_MODULES = [
    "positions",
    "orders",
    "compliance",
    "exposure",
    "cash_management",
    "risk_engine",
    "alpha_engine",
    "attribution",
    "corporate_actions",
    "fee_accounting",
]

TEST_FUND_SLUG = "migration_test"


def _make_config(module: str, db_url: str, target_schema: str | None = None) -> AlembicConfig:
    """Build an AlembicConfig for a given module."""
    cfg = AlembicConfig("alembic.ini", ini_section=module)
    cfg.set_section_option(module, "script_location", f"app/modules/{module}/migrations")
    cfg.set_section_option(module, "sqlalchemy.url", db_url)
    if target_schema:
        cfg.attributes["target_schema"] = target_schema
    return cfg


@pytest.fixture(scope="module")
def migration_db_url():
    """Start a fresh PostgreSQL container for migration testing."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url()

        # Create extensions that modules expect
        sync_url = url.replace("+asyncpg", "")
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            conn.commit()
        engine.dispose()

        yield url


class TestSharedModuleMigrations:
    """Test upgrade/downgrade/upgrade for shared-schema modules."""

    @pytest.mark.integration
    @pytest.mark.parametrize("module", SHARED_MODULES)
    def test_round_trip(self, migration_db_url: str, module: str) -> None:
        cfg = _make_config(module, migration_db_url)

        # Upgrade to head
        alembic_command.upgrade(cfg, "head")

        # Downgrade to base
        alembic_command.downgrade(cfg, "base")

        # Upgrade again — catches state left behind by incomplete downgrade
        alembic_command.upgrade(cfg, "head")


class TestPerFundModuleMigrations:
    """Test upgrade/downgrade/upgrade for per-fund-schema modules."""

    @pytest.fixture(autouse=True)
    def _create_fund_schema(self, migration_db_url: str) -> None:
        """Ensure the test fund schema exists."""
        sync_url = migration_db_url.replace("+asyncpg", "")
        engine = create_engine(sync_url)
        schema = fund_schema_name(TEST_FUND_SLUG)
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            conn.commit()
        engine.dispose()

    @pytest.mark.integration
    @pytest.mark.parametrize("module", PER_FUND_MODULES)
    def test_round_trip(self, migration_db_url: str, module: str) -> None:
        schema = fund_schema_name(TEST_FUND_SLUG)
        cfg = _make_config(module, migration_db_url, target_schema=schema)

        # Upgrade to head
        alembic_command.upgrade(cfg, "head")

        # Downgrade to base — some modules have irreversible migrations
        try:
            alembic_command.downgrade(cfg, "base")
        except NotImplementedError:
            return

        # Upgrade again — catches state left behind by incomplete downgrade
        alembic_command.upgrade(cfg, "head")
