"""AI analysis schema — analysis results and research notes.

Revision ID: 001
Revises: None
Create Date: 2026-04-08
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

SCHEMA = "platform"


def upgrade() -> None:
    # AI analysis results
    op.create_table(
        "ai_analysis_results",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("analysis_type", sa.String(32), nullable=False),
        sa.Column("request_context", PG_JSONB(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.String(16), nullable=True),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=True),
        sa.Column(
            "key_points",
            PG_JSONB(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "instruments",
            PG_JSONB(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("model_used", sa.String(64), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_analysis_type",
        "ai_analysis_results",
        ["analysis_type"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_analysis_created",
        "ai_analysis_results",
        ["created_at"],
        schema=SCHEMA,
    )

    # Research notes
    op.create_table(
        "research_notes",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("analysis_type", sa.String(32), nullable=False),
        sa.Column(
            "instruments",
            PG_JSONB(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "tags",
            PG_JSONB(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_research_notes_created",
        "research_notes",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_notes_created",
        table_name="research_notes",
        schema=SCHEMA,
    )
    op.drop_table("research_notes", schema=SCHEMA)
    op.drop_index(
        "ix_ai_analysis_created",
        table_name="ai_analysis_results",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_ai_analysis_type",
        table_name="ai_analysis_results",
        schema=SCHEMA,
    )
    op.drop_table("ai_analysis_results", schema=SCHEMA)
