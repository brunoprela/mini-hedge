"""Compliance schema — rules, violations, trade decisions.

Revision ID: 001
Revises: None
Create Date: 2026-04-03
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
    # Compliance rules
    op.create_table(
        "compliance_rules",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fund_slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("parameters", PG_JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.create_index("ix_comp_rules_fund", "compliance_rules", ["fund_slug"], schema=SCHEMA)
    op.create_index(
        "ix_comp_rules_active", "compliance_rules", ["fund_slug", "is_active"], schema=SCHEMA
    )

    # Compliance violations
    op.create_table(
        "compliance_violations",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("rule_id", PG_UUID(), nullable=False),
        sa.Column("rule_name", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.String(512), nullable=False),
        sa.Column("current_value", sa.Numeric(18, 8), nullable=True),
        sa.Column("limit_value", sa.Numeric(18, 8), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(128), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_comp_viol_portfolio", "compliance_violations", ["portfolio_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_comp_viol_rule", "compliance_violations", ["rule_id"], schema=SCHEMA
    )

    # Trade decisions (audit trail)
    op.create_table(
        "trade_decisions",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("portfolio_id", PG_UUID(), nullable=False),
        sa.Column("instrument_id", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("results", PG_JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_trade_dec_portfolio", "trade_decisions", ["portfolio_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_trade_dec_portfolio", table_name="trade_decisions", schema=SCHEMA)
    op.drop_table("trade_decisions", schema=SCHEMA)
    op.drop_index("ix_comp_viol_rule", table_name="compliance_violations", schema=SCHEMA)
    op.drop_index("ix_comp_viol_portfolio", table_name="compliance_violations", schema=SCHEMA)
    op.drop_table("compliance_violations", schema=SCHEMA)
    op.drop_index("ix_comp_rules_active", table_name="compliance_rules", schema=SCHEMA)
    op.drop_index("ix_comp_rules_fund", table_name="compliance_rules", schema=SCHEMA)
    op.drop_table("compliance_rules", schema=SCHEMA)
