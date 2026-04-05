"""Fee accounting schema — fee_schedules, fee_accruals, high_water_marks.

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

# Tables live in the "positions" logical schema, which schema_translate_map
# rewrites to the active fund schema (e.g. fund_alpha) at runtime.
SCHEMA = "positions"


def upgrade() -> None:
    # Fee schedules
    op.create_table(
        "fee_schedules",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fund_slug", sa.String(64), nullable=False, unique=True),
        sa.Column("management_fee_bps", sa.Integer(), nullable=False),
        sa.Column("performance_fee_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("hurdle_rate_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column(
            "high_water_mark",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("crystallization_frequency", sa.String(16), nullable=False),
        sa.Column("payment_frequency", sa.String(16), nullable=False),
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
        "ix_fee_schedules_fund_slug", "fee_schedules", ["fund_slug"], unique=True, schema=SCHEMA
    )

    # Fee accruals
    op.create_table(
        "fee_accruals",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("fee_type", sa.String(16), nullable=False),
        sa.Column("accrual_date", sa.Date(), nullable=False),
        sa.Column("nav_basis", sa.Numeric(20, 2), nullable=False),
        sa.Column("accrued_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("cumulative_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_fee_accruals_portfolio", "fee_accruals", ["portfolio_id"], schema=SCHEMA)
    op.create_index("ix_fee_accruals_date", "fee_accruals", ["accrual_date"], schema=SCHEMA)
    op.create_index("ix_fee_accruals_status", "fee_accruals", ["status"], schema=SCHEMA)

    # High water marks
    op.create_table(
        "high_water_marks",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("hwm_date", sa.Date(), nullable=False),
        sa.Column("hwm_nav", sa.Numeric(20, 2), nullable=False),
        sa.Column("peak_nav", sa.Numeric(20, 2), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_high_water_marks_portfolio", "high_water_marks", ["portfolio_id"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_high_water_marks_portfolio", table_name="high_water_marks", schema=SCHEMA)
    op.drop_table("high_water_marks", schema=SCHEMA)
    op.drop_index("ix_fee_accruals_status", table_name="fee_accruals", schema=SCHEMA)
    op.drop_index("ix_fee_accruals_date", table_name="fee_accruals", schema=SCHEMA)
    op.drop_index("ix_fee_accruals_portfolio", table_name="fee_accruals", schema=SCHEMA)
    op.drop_table("fee_accruals", schema=SCHEMA)
    op.drop_index("ix_fee_schedules_fund_slug", table_name="fee_schedules", schema=SCHEMA)
    op.drop_table("fee_schedules", schema=SCHEMA)
