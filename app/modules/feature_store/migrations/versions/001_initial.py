"""Feature store schema — definitions, values, and feature sets.

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
    # Feature definitions
    op.create_table(
        "feature_definitions",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_type", sa.String(16), nullable=False),
        sa.Column("compute_method", sa.String(16), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column(
            "dependencies",
            PG_JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "tags",
            PG_JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_featdef_name",
        "feature_definitions",
        ["name"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_featdef_entity_status",
        "feature_definitions",
        ["entity_type", "status"],
        schema=SCHEMA,
    )

    # Feature values
    op.create_table(
        "feature_values",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "feature_id",
            PG_UUID(),
            sa.ForeignKey("platform.feature_definitions.id"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("value_numeric", sa.Numeric(18, 8), nullable=True),
        sa.Column("value_text", sa.String(512), nullable=True),
        sa.Column("value_json", PG_JSONB(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_featval_feature_entity_ts",
        "feature_values",
        ["feature_id", "entity_id", "computed_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_featval_entity",
        "feature_values",
        ["entity_id"],
        schema=SCHEMA,
    )

    # Feature sets
    op.create_table(
        "feature_sets",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_names", PG_JSONB(), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_featset_name",
        "feature_sets",
        ["name"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_featset_name",
        table_name="feature_sets",
        schema=SCHEMA,
    )
    op.drop_table("feature_sets", schema=SCHEMA)
    op.drop_index(
        "ix_featval_entity",
        table_name="feature_values",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_featval_feature_entity_ts",
        table_name="feature_values",
        schema=SCHEMA,
    )
    op.drop_table("feature_values", schema=SCHEMA)
    op.drop_index(
        "ix_featdef_entity_status",
        table_name="feature_definitions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_featdef_name",
        table_name="feature_definitions",
        schema=SCHEMA,
    )
    op.drop_table("feature_definitions", schema=SCHEMA)
