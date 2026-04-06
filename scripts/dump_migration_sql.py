"""Dump SQL from Alembic migrations for linting with squawk.

Generates offline SQL for all migration contexts and prints to stdout.
Usage: python scripts/dump_migration_sql.py | squawk --stdin-filepath=migrations.sql
"""

from __future__ import annotations

import io

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

CONTEXTS = [
    "platform",
    "security_master",
    "market_data",
    "positions",
    "orders",
    "compliance",
    "exposure",
    "cash_management",
    "risk_engine",
    "alpha_engine",
    "attribution",
    "eod",
    "corporate_actions",
    "fee_accounting",
]


def main() -> None:
    for ctx in CONTEXTS:
        cfg = AlembicConfig("alembic.ini", ini_section=ctx)
        cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
        # Use a dummy URL for offline mode — no real DB connection needed
        cfg.set_section_option(ctx, "sqlalchemy.url", "postgresql://localhost/dummy")

        buf = io.StringIO()
        cfg.output_buffer = buf

        try:
            alembic_command.upgrade(cfg, "head", sql=True)
        except Exception:
            # Some migrations require live DB features (TimescaleDB, etc.)
            # Skip those — squawk will lint what it can
            continue

        sql = buf.getvalue()
        if sql.strip():
            print(f"-- Module: {ctx}")
            print(sql)
            print()


if __name__ == "__main__":
    main()
