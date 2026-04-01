"""Integration test fixtures — real PostgreSQL via testcontainers."""

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Start a PostgreSQL container for the test session."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest_asyncio.fixture
async def session_factory(postgres_url: str) -> async_sessionmaker[AsyncSession]:
    """Create engine + session factory, run migrations."""
    engine = create_async_engine(postgres_url, echo=False)

    # Create schemas and run migrations
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS security_master"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS market_data"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS positions"))

        migration_dir = Path("app/modules")
        for module in ["security_master", "market_data", "positions"]:
            sql_path = migration_dir / module / "migrations" / "versions" / "001_initial.sql"
            if sql_path.exists():
                await conn.execute(text(sql_path.read_text()))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()
