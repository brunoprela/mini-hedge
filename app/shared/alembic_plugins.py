"""Shared Alembic plugin configuration.

Import ``setup_plugins`` in each module's ``env.py`` to activate:
  - alembic_utils: autogenerate detection for PG functions, triggers, views
  - alembic_postgresql_enum: autogenerate detection for PG enum changes

Usage in env.py::

    from app.shared.alembic_plugins import setup_plugins
    setup_plugins()
"""

from __future__ import annotations


def setup_plugins() -> None:
    """Activate all Alembic plugins.

    Must be called at module level in env.py, before ``run_migrations_online()``.
    """
    # alembic-postgresql-enum — auto-detects enum additions/removals/renames.
    # Simply importing it registers the compare dispatch hooks.
    import alembic_postgresql_enum  # noqa: F401
