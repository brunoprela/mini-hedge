"""Integration test fixtures — real PostgreSQL via testcontainers."""

import pytest
import pytest_asyncio
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

MIGRATION_CONTEXTS = ["platform", "security_master", "market_data", "positions"]


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
async def session_factory(postgres_url: str) -> async_sessionmaker[AsyncSession]:
    """Create engine + session factory against the migrated test database."""
    engine = create_async_engine(postgres_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()
