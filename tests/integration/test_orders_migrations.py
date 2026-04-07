"""Comprehensive migration tests for the orders module.

Goes beyond the basic round-trip in test_migrations.py:
  - Step-by-step upgrade/downgrade for each revision (001→002→003→004)
  - Model-migration column alignment (ORM columns match DDL)
  - Schema isolation (fund_alpha data not visible in fund_beta)
  - Data preservation across upgrades (insert at rev N, upgrade to N+1, verify)

Uses testcontainers to spin up a real PostgreSQL 16 instance.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text

from app.shared.fund_schema import fund_schema_name

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# All revisions in order
REVISIONS = ["001", "002", "003", "004"]

# Tables created by each revision (cumulative)
TABLES_BY_REV = {
    "001": {"orders", "order_fills"},
    "002": {"orders", "order_fills"},  # only adds columns
    "003": {"orders", "order_fills", "broker_scorecards", "routing_rules", "routing_decisions"},
    "004": {
        "orders",
        "order_fills",
        "broker_scorecards",
        "routing_rules",
        "routing_decisions",
        "order_tca_results",
    },
}

# Columns added to 'orders' by each revision
ORDERS_COLUMNS_BY_REV = {
    "001": {
        "id",
        "portfolio_id",
        "instrument_id",
        "side",
        "order_type",
        "quantity",
        "filled_quantity",
        "limit_price",
        "avg_fill_price",
        "state",
        "rejection_reason",
        "compliance_results",
        "time_in_force",
        "fund_slug",
        "created_at",
        "updated_at",
    },
    "002": {"parent_order_id", "algo_type", "algo_params", "is_parent"},
    "003": {"broker_id"},
    "004": {"arrival_mid_price", "arrival_spread", "arrival_timestamp"},
}


def _make_config(db_url: str, target_schema: str) -> AlembicConfig:
    cfg = AlembicConfig("alembic.ini", ini_section="orders")
    cfg.set_section_option("orders", "script_location", "app/modules/orders/migrations")
    cfg.set_section_option("orders", "sqlalchemy.url", db_url)
    cfg.attributes["target_schema"] = target_schema
    return cfg


def _sync_url(url: str) -> str:
    return url.replace("+asyncpg", "")


def _create_schema(engine: Engine, schema: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()


def _get_table_names(engine: Engine, schema: str) -> set[str]:
    insp = inspect(engine)
    return set(insp.get_table_names(schema=schema))


def _get_column_names(engine: Engine, schema: str, table: str) -> set[str]:
    insp = inspect(engine)
    return {c["name"] for c in insp.get_columns(table, schema=schema)}


def _get_index_names(engine: Engine, schema: str, table: str) -> set[str]:
    insp = inspect(engine)
    return {idx["name"] for idx in insp.get_indexes(table, schema=schema)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_url() -> Iterator[str]:
    """Spin up a PostgreSQL container for migration tests."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url()
        # Create uuid extension
        engine = create_engine(_sync_url(url))
        with engine.connect() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            conn.commit()
        engine.dispose()
        yield url


@pytest.fixture
def engine(pg_url: str) -> Iterator[Engine]:
    eng = create_engine(_sync_url(pg_url))
    yield eng
    eng.dispose()


SCHEMA_A = fund_schema_name("alpha")
SCHEMA_B = fund_schema_name("beta")


@pytest.fixture(autouse=True)
def _clean_schemas(engine: Engine) -> Iterator[None]:
    """Drop and recreate test schemas before each test for isolation."""
    with engine.connect() as conn:
        for schema in (SCHEMA_A, SCHEMA_B):
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.commit()
    yield
    # cleanup after
    with engine.connect() as conn:
        for schema in (SCHEMA_A, SCHEMA_B):
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.commit()


# ---------------------------------------------------------------------------
# Step-by-step migration tests
# ---------------------------------------------------------------------------


class TestStepByStepMigrations:
    """Upgrade one revision at a time and verify schema state."""

    @pytest.mark.integration
    def test_upgrade_001_creates_base_tables(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "001")

        tables = _get_table_names(engine, SCHEMA_A)
        assert TABLES_BY_REV["001"] <= tables

        cols = _get_column_names(engine, SCHEMA_A, "orders")
        assert ORDERS_COLUMNS_BY_REV["001"] <= cols

        fills_cols = _get_column_names(engine, SCHEMA_A, "order_fills")
        assert {"id", "order_id", "quantity", "price", "filled_at"} <= fills_cols

    @pytest.mark.integration
    def test_upgrade_002_adds_algo_columns(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "002")

        cols = _get_column_names(engine, SCHEMA_A, "orders")
        assert ORDERS_COLUMNS_BY_REV["002"] <= cols

        idxs = _get_index_names(engine, SCHEMA_A, "orders")
        assert "ix_orders_parent_order_id" in idxs

    @pytest.mark.integration
    def test_upgrade_003_adds_broker_tables(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "003")

        tables = _get_table_names(engine, SCHEMA_A)
        assert TABLES_BY_REV["003"] <= tables

        # broker_id on orders and order_fills
        order_cols = _get_column_names(engine, SCHEMA_A, "orders")
        assert "broker_id" in order_cols
        fills_cols = _get_column_names(engine, SCHEMA_A, "order_fills")
        assert "broker_id" in fills_cols

        # Scorecard table columns
        sc_cols = _get_column_names(engine, SCHEMA_A, "broker_scorecards")
        assert {"broker_id", "fill_rate", "avg_slippage_bps", "avg_cost_bps"} <= sc_cols

    @pytest.mark.integration
    def test_upgrade_004_adds_tca(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "004")

        tables = _get_table_names(engine, SCHEMA_A)
        assert "order_tca_results" in tables

        # Arrival columns on orders
        order_cols = _get_column_names(engine, SCHEMA_A, "orders")
        assert ORDERS_COLUMNS_BY_REV["004"] <= order_cols

        # TCA results columns
        tca_cols = _get_column_names(engine, SCHEMA_A, "order_tca_results")
        expected_tca = {
            "id",
            "order_id",
            "arrival_mid_price",
            "arrival_spread",
            "vwap_benchmark",
            "total_cost_bps",
            "commission_cost_bps",
            "spread_cost_bps",
            "market_impact_cost_bps",
            "timing_cost_bps",
            "opportunity_cost_bps",
            "implementation_shortfall_bps",
            "participation_rate",
            "execution_duration_seconds",
            "total_cost_usd",
            "computed_at",
        }
        assert expected_tca <= tca_cols


# ---------------------------------------------------------------------------
# Per-revision downgrade tests
# ---------------------------------------------------------------------------


class TestDowngradeByRevision:
    """Verify each revision can cleanly downgrade."""

    @pytest.mark.integration
    def test_downgrade_004_to_003(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "004")
        alembic_command.downgrade(cfg, "003")

        tables = _get_table_names(engine, SCHEMA_A)
        assert "order_tca_results" not in tables

        order_cols = _get_column_names(engine, SCHEMA_A, "orders")
        for col in ("arrival_mid_price", "arrival_spread", "arrival_timestamp"):
            assert col not in order_cols

    @pytest.mark.integration
    def test_downgrade_003_to_002(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "003")
        alembic_command.downgrade(cfg, "002")

        tables = _get_table_names(engine, SCHEMA_A)
        for t in ("broker_scorecards", "routing_rules", "routing_decisions"):
            assert t not in tables

        order_cols = _get_column_names(engine, SCHEMA_A, "orders")
        assert "broker_id" not in order_cols

    @pytest.mark.integration
    def test_downgrade_002_to_001(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "002")
        alembic_command.downgrade(cfg, "001")

        order_cols = _get_column_names(engine, SCHEMA_A, "orders")
        for col in ("parent_order_id", "algo_type", "algo_params", "is_parent"):
            assert col not in order_cols

    @pytest.mark.integration
    def test_downgrade_001_to_base(self, pg_url: str, engine: Engine) -> None:
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "001")
        alembic_command.downgrade(cfg, "base")

        tables = _get_table_names(engine, SCHEMA_A)
        assert "orders" not in tables
        assert "order_fills" not in tables

    @pytest.mark.integration
    def test_full_down_up_round_trip(self, pg_url: str, engine: Engine) -> None:
        """Upgrade to head, downgrade all the way to base, upgrade again."""
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "head")
        alembic_command.downgrade(cfg, "base")
        alembic_command.upgrade(cfg, "head")

        tables = _get_table_names(engine, SCHEMA_A)
        assert TABLES_BY_REV["004"] <= tables


# ---------------------------------------------------------------------------
# Model-migration column alignment
# ---------------------------------------------------------------------------


class TestModelMigrationAlignment:
    """Verify ORM model columns match what migrations create in the DB."""

    @pytest.mark.integration
    def test_order_record_columns_match(self, pg_url: str, engine: Engine) -> None:
        from app.modules.orders.models import OrderRecord

        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "head")

        db_cols = _get_column_names(engine, SCHEMA_A, "orders")
        model_cols = {c.name for c in OrderRecord.__table__.columns}

        missing_in_db = model_cols - db_cols
        missing_in_model = db_cols - model_cols

        assert not missing_in_db, f"ORM columns not in DB: {missing_in_db}"
        assert not missing_in_model, f"DB columns not in ORM: {missing_in_model}"

    @pytest.mark.integration
    def test_order_fill_record_columns_match(self, pg_url: str, engine: Engine) -> None:
        from app.modules.orders.models import OrderFillRecord

        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "head")

        db_cols = _get_column_names(engine, SCHEMA_A, "order_fills")
        model_cols = {c.name for c in OrderFillRecord.__table__.columns}

        assert model_cols == db_cols, (
            f"Column mismatch: model-only={model_cols - db_cols}, db-only={db_cols - model_cols}"
        )

    @pytest.mark.integration
    def test_broker_scorecard_columns_match(self, pg_url: str, engine: Engine) -> None:
        from app.modules.orders.models import BrokerScorecardRecord

        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "head")

        db_cols = _get_column_names(engine, SCHEMA_A, "broker_scorecards")
        model_cols = {c.name for c in BrokerScorecardRecord.__table__.columns}

        assert model_cols == db_cols, (
            f"Column mismatch: model-only={model_cols - db_cols}, db-only={db_cols - model_cols}"
        )

    @pytest.mark.integration
    def test_tca_result_columns_match(self, pg_url: str, engine: Engine) -> None:
        from app.modules.orders.models import TCAResultRecord

        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "head")

        db_cols = _get_column_names(engine, SCHEMA_A, "order_tca_results")
        model_cols = {c.name for c in TCAResultRecord.__table__.columns}

        assert model_cols == db_cols, (
            f"Column mismatch: model-only={model_cols - db_cols}, db-only={db_cols - model_cols}"
        )

    @pytest.mark.integration
    def test_routing_rule_columns_match(self, pg_url: str, engine: Engine) -> None:
        from app.modules.orders.models import RoutingRuleRecord

        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "head")

        db_cols = _get_column_names(engine, SCHEMA_A, "routing_rules")
        model_cols = {c.name for c in RoutingRuleRecord.__table__.columns}

        assert model_cols == db_cols

    @pytest.mark.integration
    def test_routing_decision_columns_match(self, pg_url: str, engine: Engine) -> None:
        from app.modules.orders.models import RoutingDecisionRecord

        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "head")

        db_cols = _get_column_names(engine, SCHEMA_A, "routing_decisions")
        model_cols = {c.name for c in RoutingDecisionRecord.__table__.columns}

        assert model_cols == db_cols


# ---------------------------------------------------------------------------
# Schema isolation
# ---------------------------------------------------------------------------


class TestSchemaIsolation:
    """Verify data in one fund schema is invisible from another."""

    @pytest.mark.integration
    def test_data_isolated_between_funds(self, pg_url: str, engine: Engine) -> None:
        """Insert an order in fund_alpha, verify it's not in fund_beta."""
        # Migrate both schemas
        for schema in (SCHEMA_A, SCHEMA_B):
            cfg = _make_config(pg_url, schema)
            alembic_command.upgrade(cfg, "head")

        with engine.connect() as conn:
            # Insert into fund_alpha
            conn.execute(
                text(f"""
                INSERT INTO {SCHEMA_A}.orders (
                    portfolio_id, instrument_id, side, order_type,
                    quantity, state, time_in_force, fund_slug
                ) VALUES (
                    gen_random_uuid(), 'AAPL', 'buy', 'market',
                    100, 'new', 'day', 'alpha'
                )
            """)
            )
            conn.commit()

            # Verify present in alpha
            alpha_count = conn.execute(text(f"SELECT count(*) FROM {SCHEMA_A}.orders")).scalar()
            assert alpha_count == 1

            # Verify absent in beta
            beta_count = conn.execute(text(f"SELECT count(*) FROM {SCHEMA_B}.orders")).scalar()
            assert beta_count == 0

    @pytest.mark.integration
    def test_independent_migration_versions(self, pg_url: str, engine: Engine) -> None:
        """Each schema tracks its own alembic version independently."""
        # Migrate alpha to head, beta only to 002
        cfg_a = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg_a, "head")

        cfg_b = _make_config(pg_url, SCHEMA_B)
        alembic_command.upgrade(cfg_b, "002")

        with engine.connect() as conn:
            ver_a = conn.execute(
                text(f"SELECT version_num FROM {SCHEMA_A}.alembic_version_orders")
            ).scalar()
            ver_b = conn.execute(
                text(f"SELECT version_num FROM {SCHEMA_B}.alembic_version_orders")
            ).scalar()

        assert ver_a == "004"
        assert ver_b == "002"

        # beta should NOT have broker tables
        tables_b = _get_table_names(engine, SCHEMA_B)
        assert "broker_scorecards" not in tables_b


# ---------------------------------------------------------------------------
# Data preservation across upgrades
# ---------------------------------------------------------------------------


class TestDataPreservation:
    """Insert data at one revision, upgrade, verify data survives."""

    @pytest.mark.integration
    def test_order_survives_002_upgrade(self, pg_url: str, engine: Engine) -> None:
        """Insert an order at rev 001, upgrade to 002, verify data intact."""
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "001")

        # Insert a test order
        with engine.connect() as conn:
            conn.execute(
                text(f"""
                INSERT INTO {SCHEMA_A}.orders (
                    portfolio_id, instrument_id, side, order_type,
                    quantity, state, time_in_force, fund_slug
                ) VALUES (
                    gen_random_uuid(), 'MSFT', 'sell', 'limit',
                    500, 'filled', 'gtc', 'alpha'
                )
            """)
            )
            conn.commit()

        # Upgrade to 002
        alembic_command.upgrade(cfg, "002")

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT instrument_id, quantity, state, algo_type, is_parent"
                    f" FROM {SCHEMA_A}.orders"
                )
            ).fetchone()

        assert row is not None
        assert row[0] == "MSFT"
        assert row[1] == Decimal("500.00000000")
        assert row[2] == "filled"
        assert row[3] is None  # algo_type defaults to NULL
        assert row[4] is False  # is_parent defaults to false

    @pytest.mark.integration
    def test_order_survives_003_upgrade(self, pg_url: str, engine: Engine) -> None:
        """Insert order+fill at rev 002, upgrade to 003, verify data."""
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "002")

        with engine.connect() as conn:
            conn.execute(
                text(f"""
                INSERT INTO {SCHEMA_A}.orders (
                    id, portfolio_id, instrument_id, side, order_type,
                    quantity, filled_quantity, avg_fill_price,
                    state, time_in_force, fund_slug
                ) VALUES (
                    'a0000000-0000-0000-0000-000000000001',
                    gen_random_uuid(), 'GOOG', 'buy', 'market',
                    1000, 1000, 150.25,
                    'filled', 'day', 'alpha'
                )
            """)
            )
            conn.execute(
                text(f"""
                INSERT INTO {SCHEMA_A}.order_fills (
                    order_id, quantity, price
                ) VALUES (
                    'a0000000-0000-0000-0000-000000000001', 1000, 150.25
                )
            """)
            )
            conn.commit()

        alembic_command.upgrade(cfg, "003")

        test_id = "a0000000-0000-0000-0000-000000000001"
        with engine.connect() as conn:
            order = conn.execute(
                text(
                    f"SELECT instrument_id, broker_id FROM {SCHEMA_A}.orders WHERE id = '{test_id}'"
                )
            ).fetchone()
            fill = conn.execute(
                text(
                    f"SELECT quantity, broker_id"
                    f" FROM {SCHEMA_A}.order_fills"
                    f" WHERE order_id = '{test_id}'"
                )
            ).fetchone()

        assert order is not None
        assert order[0] == "GOOG"
        assert order[1] is None  # broker_id defaults to NULL
        assert fill is not None
        assert fill[0] == Decimal("1000.00000000")
        assert fill[1] is None

    @pytest.mark.integration
    def test_order_survives_004_upgrade(self, pg_url: str, engine: Engine) -> None:
        """Insert order at rev 003, upgrade to 004, verify arrival columns null."""
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "003")

        with engine.connect() as conn:
            conn.execute(
                text(f"""
                INSERT INTO {SCHEMA_A}.orders (
                    portfolio_id, instrument_id, side, order_type,
                    quantity, state, time_in_force, fund_slug, broker_id
                ) VALUES (
                    gen_random_uuid(), 'TSLA', 'buy', 'market',
                    200, 'new', 'day', 'alpha', 'GS'
                )
            """)
            )
            conn.commit()

        alembic_command.upgrade(cfg, "004")

        with engine.connect() as conn:
            row = conn.execute(
                text(f"""
                    SELECT instrument_id, broker_id,
                           arrival_mid_price, arrival_spread, arrival_timestamp
                    FROM {SCHEMA_A}.orders
                """)
            ).fetchone()

        assert row is not None
        assert row[0] == "TSLA"
        assert row[1] == "GS"
        assert row[2] is None  # arrival_mid_price
        assert row[3] is None  # arrival_spread
        assert row[4] is None  # arrival_timestamp

    @pytest.mark.integration
    def test_full_lifecycle_data_survives(self, pg_url: str, engine: Engine) -> None:
        """Insert data at rev 001, upgrade through all revisions, verify everything."""
        cfg = _make_config(pg_url, SCHEMA_A)
        alembic_command.upgrade(cfg, "001")

        # Insert order + fill at rev 001
        with engine.connect() as conn:
            conn.execute(
                text(f"""
                INSERT INTO {SCHEMA_A}.orders (
                    id, portfolio_id, instrument_id, side, order_type,
                    quantity, filled_quantity, avg_fill_price,
                    state, time_in_force, fund_slug
                ) VALUES (
                    'b0000000-0000-0000-0000-000000000001',
                    gen_random_uuid(), 'AMZN', 'buy', 'market',
                    750, 750, 180.50,
                    'filled', 'day', 'alpha'
                )
            """)
            )
            conn.execute(
                text(f"""
                INSERT INTO {SCHEMA_A}.order_fills (
                    order_id, quantity, price
                ) VALUES (
                    'b0000000-0000-0000-0000-000000000001', 750, 180.50
                )
            """)
            )
            conn.commit()

        # Upgrade through all revisions
        alembic_command.upgrade(cfg, "head")

        with engine.connect() as conn:
            order = conn.execute(
                text(f"""
                    SELECT instrument_id, quantity, state,
                           parent_order_id, algo_type, is_parent,
                           broker_id,
                           arrival_mid_price, arrival_spread
                    FROM {SCHEMA_A}.orders
                    WHERE id = 'b0000000-0000-0000-0000-000000000001'
                """)
            ).fetchone()
            fill = conn.execute(
                text(f"""
                    SELECT quantity, price, broker_id
                    FROM {SCHEMA_A}.order_fills
                    WHERE order_id = 'b0000000-0000-0000-0000-000000000001'
                """)
            ).fetchone()

        # Original data intact
        assert order[0] == "AMZN"
        assert order[1] == Decimal("750.00000000")
        assert order[2] == "filled"
        # 002 defaults
        assert order[3] is None  # parent_order_id
        assert order[4] is None  # algo_type
        assert order[5] is False  # is_parent
        # 003 defaults
        assert order[6] is None  # broker_id
        # 004 defaults
        assert order[7] is None  # arrival_mid_price
        assert order[8] is None  # arrival_spread

        assert fill[0] == Decimal("750.00000000")
        assert fill[1] == Decimal("180.50000000")
        assert fill[2] is None  # broker_id (added in 003)
