"""Multi-schema Alembic environment.

Supports running migrations for individual bounded contexts:
    alembic -n security_master upgrade head
    alembic -n market_data upgrade head
    alembic -n positions upgrade head
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()


def get_schema_for_section() -> str:
    """Determine which schema to migrate based on the alembic -n section."""
    section = config.config_ini_section
    schema_map = {
        "security_master": "security_master",
        "market_data": "market_data",
        "positions": "positions",
    }
    return schema_map.get(section, "public")


def run_migrations_offline() -> None:
    url = settings.database_url
    schema = get_schema_for_section()
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema,
        include_schemas=[schema],
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    schema = get_schema_for_section()
    context.configure(
        connection=connection,
        target_metadata=None,
        version_table_schema=schema,
        include_schemas=[schema],
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )
    schema = get_schema_for_section()
    async with engine.connect() as connection:
        await connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await connection.commit()
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
