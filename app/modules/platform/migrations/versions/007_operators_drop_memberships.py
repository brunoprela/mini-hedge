"""Add operators table, drop fund_memberships.

Authorization relationships now live entirely in OpenFGA. The
fund_memberships table is replaced by FGA tuples
(user:{id} -> role -> fund:{id}).

Revision ID: 007
Revises: 006
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create operators table
    op.create_table(
        "operators",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("keycloak_sub", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("keycloak_sub"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_operators_email", "operators", ["email"], unique=True, schema="platform"
    )
    op.create_index(
        "ix_platform_operators_keycloak_sub",
        "operators",
        ["keycloak_sub"],
        unique=True,
        schema="platform",
    )

    # Drop fund_memberships — authorization now lives in FGA
    op.drop_table("fund_memberships", schema="platform")


def downgrade() -> None:
    # Recreate fund_memberships
    op.create_table(
        "fund_memberships",
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("platform.users.id"),
            nullable=False,
        ),
        sa.Column(
            "fund_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("platform.funds.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "fund_id"),
        schema="platform",
    )

    # Drop operators
    op.drop_index("ix_platform_operators_keycloak_sub", table_name="operators", schema="platform")
    op.drop_index("ix_platform_operators_email", table_name="operators", schema="platform")
    op.drop_table("operators", schema="platform")
