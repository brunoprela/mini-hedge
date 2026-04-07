"""Add parent/child order support for algorithmic execution.

Parent orders represent the PM's intent (e.g. "buy 100,000 AAPL via TWAP").
Child orders are the individual slices submitted to the broker.

Revision ID: 002
Revises: 001
Create Date: 2026-04-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
PG_JSONB = sa.dialects.postgresql.JSONB

# Logical schema name used in ORM models.  At runtime the env.py's
# schema_translate_map remaps this to the real fund schema (fund_alpha,
# etc.).  However, Alembic's add_column / create_index emit literal SQL
# that bypasses schema_translate_map, so we resolve the *actual* target
# schema at migration time instead.
_LOGICAL_SCHEMA = "positions"


def _schema() -> str:
    """Return the real target schema for this migration run."""
    conn = op.get_bind()
    stm = getattr(conn, "_execution_options", {}).get("schema_translate_map", {})
    return str(stm.get(_LOGICAL_SCHEMA, _LOGICAL_SCHEMA))


def upgrade() -> None:
    schema = _schema()

    op.add_column(
        "orders",
        sa.Column(
            "parent_order_id",
            PG_UUID(),
            nullable=True,
        ),
        schema=schema,
    )
    # Self-referential FK added separately to use the resolved schema
    op.create_foreign_key(
        "fk_orders_parent_order_id",
        "orders",
        "orders",
        ["parent_order_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.add_column(
        "orders",
        sa.Column("algo_type", sa.String(16), nullable=True),
        schema=schema,
    )
    op.add_column(
        "orders",
        sa.Column("algo_params", PG_JSONB(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "orders",
        sa.Column(
            "is_parent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_orders_parent_order_id",
        "orders",
        ["parent_order_id"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()

    op.drop_index(
        "ix_orders_parent_order_id",
        table_name="orders",
        schema=schema,
    )
    op.drop_column("orders", "is_parent", schema=schema)
    op.drop_column("orders", "algo_params", schema=schema)
    op.drop_column("orders", "algo_type", schema=schema)
    op.drop_constraint(
        "fk_orders_parent_order_id",
        "orders",
        schema=schema,
    )
    op.drop_column("orders", "parent_order_id", schema=schema)
