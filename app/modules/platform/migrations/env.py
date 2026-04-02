"""Alembic environment for the platform bounded context."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from app.modules.platform.models import Base

SCHEMA = "platform"

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Resolve database URL: alembic config override > app settings.

    Converts async URLs (asyncpg) to sync (psycopg2) for Alembic.
    """
    url = config.get_section_option(config.config_ini_section, "sqlalchemy.url")
    if url:
        return url
    from app.config import get_settings

    raw = get_settings().database_url
    return raw.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=SCHEMA,
        include_schemas=[SCHEMA],
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    # Bypass RLS policies during migrations
    connection.execute(text("SET app.current_fund_id = 'BYPASS'"))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=SCHEMA,
        include_schemas=[SCHEMA],
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.commit()
        do_run_migrations(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
