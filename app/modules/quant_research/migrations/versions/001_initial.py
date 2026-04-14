"""Quant research schema — factors, exposures, returns, regime detection.

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
    # Factor definitions
    op.create_table(
        "factor_definitions",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("factor_type", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("parameters", PG_JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )

    # Factor exposures
    op.create_table(
        "factor_exposures",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "factor_id",
            PG_UUID(),
            sa.ForeignKey("platform.factor_definitions.id"),
            nullable=False,
        ),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("exposure", sa.Numeric(12, 6), nullable=False),
        sa.Column("z_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fexp_factor_date",
        "factor_exposures",
        ["factor_id", "as_of_date"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fexp_instrument",
        "factor_exposures",
        ["instrument_id"],
        schema=SCHEMA,
    )

    # Factor returns
    op.create_table(
        "factor_returns",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "factor_id",
            PG_UUID(),
            sa.ForeignKey("platform.factor_definitions.id"),
            nullable=False,
        ),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("return_pct", sa.Numeric(12, 8), nullable=False),
        sa.Column("cumulative_return", sa.Numeric(12, 8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fret_factor_date",
        "factor_returns",
        ["factor_id", "return_date"],
        schema=SCHEMA,
    )

    # Regime snapshots
    op.create_table(
        "regime_snapshots",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("regime_type", sa.String(32), nullable=False),
        sa.Column("detection_method", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("indicators", PG_JSONB(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_regime_start_date",
        "regime_snapshots",
        ["start_date"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regime_start_date",
        table_name="regime_snapshots",
        schema=SCHEMA,
    )
    op.drop_table("regime_snapshots", schema=SCHEMA)
    op.drop_index(
        "ix_fret_factor_date",
        table_name="factor_returns",
        schema=SCHEMA,
    )
    op.drop_table("factor_returns", schema=SCHEMA)
    op.drop_index(
        "ix_fexp_instrument",
        table_name="factor_exposures",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_fexp_factor_date",
        table_name="factor_exposures",
        schema=SCHEMA,
    )
    op.drop_table("factor_exposures", schema=SCHEMA)
    op.drop_table("factor_definitions", schema=SCHEMA)
