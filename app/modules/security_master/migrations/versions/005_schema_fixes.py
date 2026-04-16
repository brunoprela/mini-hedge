"""Schema fixes: cascade deletes on extensions, FK constraints on underlying_id,
Float→Numeric for spread_bps, drop redundant ticker unique constraint,
add updated_at to extension tables.

Revision ID: 005
Revises: 004
Create Date: 2026-04-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "security_master"

# All extension tables that need CASCADE on their instrument_id FK
_EXTENSION_TABLES = [
    "equity_extensions",
    "fixed_income_extensions",
    "future_extensions",
    "fx_extensions",
    "option_extensions",
    "swap_extensions",
]

# Tables with underlying_id that need a FK to instruments
_UNDERLYING_TABLES = [
    "future_extensions",
    "option_extensions",
    "swap_extensions",
]


def upgrade() -> None:
    # 1. Add ondelete="CASCADE" to all extension instrument_id FKs
    for table in _EXTENSION_TABLES:
        # Drop the existing FK and re-create with CASCADE
        # Convention: fk name is {table}_instrument_id_fkey
        fk_name = f"{table}_instrument_id_fkey"
        op.drop_constraint(fk_name, table, schema=_SCHEMA, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            "instruments",
            ["instrument_id"],
            ["id"],
            source_schema=_SCHEMA,
            referent_schema=_SCHEMA,
            ondelete="CASCADE",
        )

    # 2. Add FK constraints on underlying_id columns
    for table in _UNDERLYING_TABLES:
        fk_name = f"{table}_underlying_id_fkey"
        op.create_foreign_key(
            fk_name,
            table,
            "instruments",
            ["underlying_id"],
            ["id"],
            source_schema=_SCHEMA,
            referent_schema=_SCHEMA,
            ondelete="SET NULL",
        )

    # 3. Change spread_bps from Float to Numeric (precision matters for pricing)
    op.alter_column(
        "instruments",
        "spread_bps",
        type_=sa.Numeric(precision=10, scale=4),
        existing_type=sa.Float(),
        existing_nullable=True,
        schema=_SCHEMA,
    )

    # 4. Drop redundant unique=True on ticker column (ix_sm_instruments_ticker
    #    already enforces uniqueness via the named index in __table_args__)
    op.drop_constraint("instruments_ticker_key", "instruments", schema=_SCHEMA, type_="unique")

    # 5. Add updated_at to all extension tables
    for table in _EXTENSION_TABLES:
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            schema=_SCHEMA,
        )


def downgrade() -> None:
    # 5. Remove updated_at from extension tables
    for table in _EXTENSION_TABLES:
        op.drop_column(table, "updated_at", schema=_SCHEMA)

    # 4. Re-add redundant unique constraint on ticker
    op.create_unique_constraint(
        "instruments_ticker_key", "instruments", ["ticker"], schema=_SCHEMA
    )

    # 3. Revert spread_bps back to Float
    op.alter_column(
        "instruments",
        "spread_bps",
        type_=sa.Float(),
        existing_type=sa.Numeric(precision=10, scale=4),
        existing_nullable=True,
        schema=_SCHEMA,
    )

    # 2. Drop underlying_id FK constraints
    for table in _UNDERLYING_TABLES:
        op.drop_constraint(f"{table}_underlying_id_fkey", table, schema=_SCHEMA, type_="foreignkey")

    # 1. Revert extension FKs to no CASCADE
    for table in _EXTENSION_TABLES:
        fk_name = f"{table}_instrument_id_fkey"
        op.drop_constraint(fk_name, table, schema=_SCHEMA, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            "instruments",
            ["instrument_id"],
            ["id"],
            source_schema=_SCHEMA,
            referent_schema=_SCHEMA,
        )
