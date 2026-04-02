"""Add keycloak_sub column to users, drop mfa_verified.

Revision ID: 003
Revises: 002
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("keycloak_sub", sa.String(255), nullable=True),
        schema="platform",
    )
    op.create_index(
        "ix_platform_users_keycloak_sub",
        "users",
        ["keycloak_sub"],
        unique=True,
        schema="platform",
    )
    op.drop_column("users", "mfa_verified", schema="platform")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default="false"),
        schema="platform",
    )
    op.drop_index(
        "ix_platform_users_keycloak_sub",
        table_name="users",
        schema="platform",
    )
    op.drop_column("users", "keycloak_sub", schema="platform")
