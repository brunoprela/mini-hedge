"""Auth tables — users, API keys, fund memberships.

Revision ID: 002
Revises: 001
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "mfa_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_users_email",
        "users",
        ["email"],
        unique=True,
        schema="platform",
    )

    op.create_table(
        "fund_memberships",
        sa.Column(
            "user_id",
            PG_UUID(),
            sa.ForeignKey("platform.users.id"),
            nullable=False,
        ),
        sa.Column(
            "fund_id",
            PG_UUID(),
            sa.ForeignKey("platform.funds.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("user_id", "fund_id"),
        schema="platform",
    )

    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            PG_UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "key_hash",
            sa.String(64),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "actor_type",
            sa.String(16),
            nullable=False,
            server_default="apikey",
        ),
        sa.Column(
            "fund_id",
            PG_UUID(),
            sa.ForeignKey("platform.funds.id"),
            nullable=False,
        ),
        sa.Column(
            "roles",
            sa.dialects.postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            PG_UUID(),
            sa.ForeignKey("platform.users.id"),
            nullable=True,
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_api_keys_hash",
        "api_keys",
        ["key_hash"],
        unique=True,
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("api_keys", schema="platform")
    op.drop_table("fund_memberships", schema="platform")
    op.drop_table("users", schema="platform")
