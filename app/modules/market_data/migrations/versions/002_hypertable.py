"""Convert prices to a TimescaleDB hypertable for time-series performance.

Revision ID: 002
Revises: 001
Create Date: 2026-04-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Only convert to hypertable if TimescaleDB extension is available.
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
    if result.scalar() is not None:
        op.execute(
            "SELECT create_hypertable("
            "'market_data.prices', 'timestamp', "
            "if_not_exists => TRUE, "
            "migrate_data => TRUE"
            ")"
        )


def downgrade() -> None:
    # TimescaleDB doesn't support reverting a hypertable to a regular table.
    # The table itself remains usable; just lose chunking benefits.
    pass
