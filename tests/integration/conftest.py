"""Integration test fixtures — real PostgreSQL via testcontainers.

Sets up a multi-fund environment with three funds, each with their own
per-fund PostgreSQL schema, portfolios, and API keys.  Shared data
(security_master, market_data) is migrated once.
"""

import pytest
import pytest_asyncio
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.platform.models import Base as PlatformBase
from app.modules.platform.seed import (
    FUND_ALPHA_ID,
    FUND_BETA_ID,
    FUND_GAMMA_ID,
    PORTFOLIO_ALPHA_EQUITY_LS_ID,
    PORTFOLIO_BETA_STAT_ARB_ID,
    PORTFOLIO_GAMMA_EVENT_DRIVEN_ID,
    build_seed_api_keys,
    build_seed_funds,
    build_seed_operators,
    build_seed_portfolios,
    build_seed_users,
)
from app.shared.database import TenantSessionFactory
from app.shared.fund_schema import fund_schema_name
from app.shared.request_context import ActorType, RequestContext, set_request_context

# Shared migrations — positions are per-fund, created below.
MIGRATION_CONTEXTS = ["platform", "security_master", "market_data"]

# All three test funds — each gets a per-fund schema
TEST_FUND_SLUGS = ["alpha", "beta", "gamma"]


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Start a PostgreSQL container, run migrations, seed platform data."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url()
        sync_url = url.replace("+asyncpg", "")

        # 1. Run shared Alembic migrations for each bounded context.
        for ctx in MIGRATION_CONTEXTS:
            cfg = AlembicConfig("alembic.ini", ini_section=ctx)
            cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
            cfg.set_section_option(ctx, "sqlalchemy.url", url)
            alembic_command.upgrade(cfg, "head")

        # 2. Seed platform data (funds, portfolios, users, operators, API keys)
        engine = create_engine(sync_url)
        _seed_platform_sync(engine)

        # 3. Create per-fund schemas and run positions migrations for each
        for slug in TEST_FUND_SLUGS:
            schema = fund_schema_name(slug)
            with engine.connect() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
                conn.commit()

            cfg = AlembicConfig("alembic.ini", ini_section="positions")
            cfg.set_section_option(
                "positions", "script_location", "app/modules/positions/migrations"
            )
            cfg.set_section_option("positions", "sqlalchemy.url", url)
            cfg.attributes["target_schema"] = schema
            alembic_command.upgrade(cfg, "head")

        engine.dispose()

        yield url


def _seed_platform_sync(engine) -> None:  # type: ignore[no-untyped-def]
    """Insert seed data into the platform schema using sync engine."""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        # Funds
        for fund in build_seed_funds():
            session.execute(
                PlatformBase.metadata.tables["platform.funds"]
                .insert()
                .values(
                    id=fund.id,
                    slug=fund.slug,
                    name=fund.name,
                    status=fund.status,
                    base_currency=fund.base_currency,
                )
            )

        # Portfolios
        for p in build_seed_portfolios():
            session.execute(
                PlatformBase.metadata.tables["platform.portfolios"]
                .insert()
                .values(
                    id=p.id,
                    fund_id=p.fund_id,
                    slug=p.slug,
                    name=p.name,
                    strategy=p.strategy,
                )
            )

        # Users
        for u in build_seed_users():
            session.execute(
                PlatformBase.metadata.tables["platform.users"]
                .insert()
                .values(
                    id=u.id,
                    email=u.email,
                    name=u.name,
                    is_active=u.is_active,
                )
            )

        # Operators
        for op in build_seed_operators():
            session.execute(
                PlatformBase.metadata.tables["platform.operators"]
                .insert()
                .values(
                    id=op.id,
                    email=op.email,
                    name=op.name,
                    is_active=op.is_active,
                )
            )

        # API keys
        for k in build_seed_api_keys():
            session.execute(
                PlatformBase.metadata.tables["platform.api_keys"]
                .insert()
                .values(
                    id=k.id,
                    key_hash=k.key_hash,
                    name=k.name,
                    actor_type=k.actor_type,
                    fund_id=k.fund_id,
                    roles=k.roles,
                )
            )

        session.commit()


@pytest_asyncio.fixture
async def session_factory(postgres_url: str) -> TenantSessionFactory:
    """Create engine + tenant session factory against the migrated test database."""
    engine = create_async_engine(postgres_url, echo=False)
    yield TenantSessionFactory(engine)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Request contexts — one per fund, autouse default is fund-alpha
# ---------------------------------------------------------------------------


def _make_context(
    fund_slug: str,
    fund_id: str,
    actor_id: str = "test-user",
    roles: frozenset[str] | None = None,
) -> RequestContext:
    return RequestContext(
        actor_id=actor_id,
        actor_type=ActorType.USER,
        fund_slug=fund_slug,
        fund_id=fund_id,
        roles=roles or frozenset({"admin"}),
        permissions=frozenset(),
    )


@pytest.fixture(autouse=True)
def request_context() -> RequestContext:
    """Default request context — fund-alpha, admin role."""
    ctx = _make_context("alpha", FUND_ALPHA_ID)
    set_request_context(ctx)
    return ctx


@pytest.fixture
def alpha_context() -> RequestContext:
    """Explicit fund-alpha context."""
    ctx = _make_context("alpha", FUND_ALPHA_ID)
    set_request_context(ctx)
    return ctx


@pytest.fixture
def beta_context() -> RequestContext:
    """Fund-beta context (Bridgewater Systematic)."""
    ctx = _make_context("beta", FUND_BETA_ID, actor_id="beta-pm")
    set_request_context(ctx)
    return ctx


@pytest.fixture
def gamma_context() -> RequestContext:
    """Fund-gamma context (Citrine Event-Driven)."""
    ctx = _make_context("gamma", FUND_GAMMA_ID, actor_id="gamma-pm")
    set_request_context(ctx)
    return ctx


# ---------------------------------------------------------------------------
# Convenience: well-known portfolio IDs for tests
# ---------------------------------------------------------------------------

ALPHA_PORTFOLIO_ID = PORTFOLIO_ALPHA_EQUITY_LS_ID
BETA_PORTFOLIO_ID = PORTFOLIO_BETA_STAT_ARB_ID
GAMMA_PORTFOLIO_ID = PORTFOLIO_GAMMA_EVENT_DRIVEN_ID
