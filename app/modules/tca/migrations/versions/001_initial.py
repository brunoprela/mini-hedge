"""TCA schema — baseline migration (table created by orders/004_tca).

The ``order_tca_results`` table is created by the orders module migration
004_tca.py.  This migration exists only to establish the TCA alembic
version chain so future TCA-specific migrations can build on it.

Revision ID: 001
Revises: None
Create Date: 2026-04-13
"""

from collections.abc import Sequence

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
