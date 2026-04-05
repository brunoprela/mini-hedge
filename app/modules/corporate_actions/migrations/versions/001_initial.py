"""Corporate actions schema — processed corporate actions.

Revision ID: 001
Revises: None
Create Date: 2026-04-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
PG_JSONB = sa.dialects.postgresql.JSONB

# Tables live in the "positions" logical schema, which schema_translate_map
# rewrites to the active fund schema (e.g. fund_alpha) at runtime.
SCHEMA = "positions"


def upgrade() -> None:
    op.create_table(
        "processed_corporate_actions",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("action_id", sa.String(128), nullable=False, unique=True),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("adjustments", PG_JSONB(), nullable=True),
        sa.Column("error_message", sa.String(512), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pca_action_id",
        "processed_corporate_actions",
        ["action_id"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pca_instrument",
        "processed_corporate_actions",
        ["instrument_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pca_status",
        "processed_corporate_actions",
        ["status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_pca_status", table_name="processed_corporate_actions", schema=SCHEMA)
    op.drop_index("ix_pca_instrument", table_name="processed_corporate_actions", schema=SCHEMA)
    op.drop_index("ix_pca_action_id", table_name="processed_corporate_actions", schema=SCHEMA)
    op.drop_table("processed_corporate_actions", schema=SCHEMA)
