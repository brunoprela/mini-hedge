"""Add stop_price to orders, commission + venue to order_fills.

Supports STOP/STOP_LIMIT order types and per-fill cost/venue tracking.

Revision ID: 005
Revises: 004
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
        sa.Column("stop_price", sa.Numeric(18, 8), nullable=True),
        schema=schema,
    )
    op.add_column(
        "order_fills",
        sa.Column("commission", sa.Numeric(18, 8), nullable=True),
        schema=schema,
    )
    op.add_column(
        "order_fills",
        sa.Column("venue", sa.String(64), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()
    op.drop_column("order_fills", "venue", schema=schema)
    op.drop_column("order_fills", "commission", schema=schema)
    op.drop_column("orders", "stop_price", schema=schema)
