"""Add keycloak_sub column to investors table for JIT Keycloak sync.

Revision ID: 018
Revises: 017
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investors",
        sa.Column("keycloak_sub", sa.String(255), nullable=True, unique=True),
        schema="platform",
    )


def downgrade() -> None:
    op.drop_column("investors", "keycloak_sub", schema="platform")
