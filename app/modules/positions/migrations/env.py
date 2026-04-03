"""Alembic environment for the positions bounded context.

Supports per-fund schema isolation.  When ``target_schema`` is set on the
Alembic config attributes (by ``FundSchemaManager``), tables are created in
that schema instead of the default ``positions``.  Each fund schema gets its
own ``alembic_version`` table so migrations are tracked independently.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from app.modules.positions.models import Base

DEFAULT_SCHEMA = "positions"

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_target_schema() -> str:
    """Resolve the target schema: explicit override or default."""
    return getattr(config.attributes, "target_schema", None) or config.attributes.get(
        "target_schema", DEFAULT_SCHEMA
    )


def _get_url() -> str:
    """Resolve database URL: alembic config override > app settings.

    Converts async URLs (asyncpg) to sync (psycopg2) for Alembic.
    """
    url = config.get_section_option(config.config_ini_section, "sqlalchemy.url")
    if url:
        return url.replace("+asyncpg", "")
    from app.config import get_settings

    raw = get_settings().database_url
    return raw.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    schema = _get_target_schema()
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema,
        include_schemas=[schema],
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection, schema: str) -> None:  # type: ignore[no-untyped-def]
    # Apply schema_translate_map so migration ops target the right schema
    if schema != DEFAULT_SCHEMA:
        connection = connection.execution_options(
            schema_translate_map={DEFAULT_SCHEMA: schema},
        )
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=schema,
        include_schemas=[schema],
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    schema = _get_target_schema()
    if schema == DEFAULT_SCHEMA:
        raise RuntimeError(
            "Positions migrations must target a per-fund schema. "
            "Set target_schema via Alembic config attributes."
        )
    engine = create_engine(_get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        connection.commit()
        do_run_migrations(connection, schema)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
