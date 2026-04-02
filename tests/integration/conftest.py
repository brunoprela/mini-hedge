"""Integration test fixtures — real PostgreSQL via testcontainers."""

import pytest
import pytest_asyncio
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.shared.database import TenantSessionFactory
from app.shared.request_context import ActorType, RequestContext, set_request_context

MIGRATION_CONTEXTS = ["platform", "security_master", "market_data", "positions"]

# Matches the seeded fund UUID from app/modules/platform/seed.py
_TEST_FUND_ID = "10000000-0000-0000-0000-000000000001"
_TEST_FUND_SLUG = "fund-alpha"


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Start a PostgreSQL container and run Alembic migrations."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url()

        # Run Alembic migrations for each bounded context.
        # Override sqlalchemy.url so env.py uses the test database.
        for ctx in MIGRATION_CONTEXTS:
            cfg = AlembicConfig("alembic.ini", ini_section=ctx)
            cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
            cfg.set_section_option(ctx, "sqlalchemy.url", url)
            alembic_command.upgrade(cfg, "head")

        yield url


@pytest_asyncio.fixture
async def session_factory(postgres_url: str) -> TenantSessionFactory:
    """Create engine + tenant session factory against the migrated test database."""
    engine = create_async_engine(postgres_url, echo=False)
    raw_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield TenantSessionFactory(raw_factory)
    await engine.dispose()


@pytest.fixture(autouse=True)
def request_context() -> RequestContext:
    """Set and return a default request context for integration tests.

    Provides fund_id so the TenantSessionFactory sets the correct
    RLS session variable. Tests that call services pass this ctx explicitly.
    """
    ctx = RequestContext(
        actor_id="test-user",
        actor_type=ActorType.USER,
        fund_slug=_TEST_FUND_SLUG,
        fund_id=_TEST_FUND_ID,
        roles=frozenset({"admin"}),
        permissions=frozenset(),
    )
    set_request_context(ctx)
    return ctx
