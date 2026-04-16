"""Add updated_at to customers and funds, unique constraint on portfolio slug per fund.

Revision ID: 019
Revises: 018
Create Date: 2026-04-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "platform"


def upgrade() -> None:
    # 1. Add updated_at to customers
    op.add_column(
        "customers",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=_SCHEMA,
    )

    # 2. Add updated_at to funds
    op.add_column(
        "funds",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=_SCHEMA,
    )

    # 3. Add composite unique constraint on (fund_id, slug) for portfolios
    op.create_unique_constraint(
        "uq_portfolios_fund_slug",
        "portfolios",
        ["fund_id", "slug"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("uq_portfolios_fund_slug", "portfolios", schema=_SCHEMA, type_="unique")
    op.drop_column("funds", "updated_at", schema=_SCHEMA)
    op.drop_column("customers", "updated_at", schema=_SCHEMA)
