"""Add OHLCV continuous aggregates on the prices hypertable.

Revision ID: 003
Revises: 002
Create Date: 2026-04-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
    if result.scalar() is None:
        return

    # 1-minute OHLCV bars
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS market_data.ohlcv_1m
        WITH (timescaledb.continuous) AS
        SELECT
          time_bucket('1 minute', timestamp) AS bucket,
          instrument_id,
          first(mid, timestamp) AS open,
          max(mid) AS high,
          min(mid) AS low,
          last(mid, timestamp) AS close,
          sum(coalesce(volume, 0)) AS volume,
          count(*) AS tick_count
        FROM market_data.prices
        GROUP BY bucket, instrument_id
        WITH NO DATA
        """
    )

    # Daily OHLCV bars
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS market_data.ohlcv_1d
        WITH (timescaledb.continuous) AS
        SELECT
          time_bucket('1 day', timestamp) AS bucket,
          instrument_id,
          first(mid, timestamp) AS open,
          max(mid) AS high,
          min(mid) AS low,
          last(mid, timestamp) AS close,
          sum(coalesce(volume, 0)) AS volume,
          count(*) AS tick_count
        FROM market_data.prices
        GROUP BY bucket, instrument_id
        WITH NO DATA
        """
    )

    # Refresh policies
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('market_data.ohlcv_1m',
          start_offset => INTERVAL '2 minutes',
          end_offset   => INTERVAL '0 minutes',
          schedule_interval => INTERVAL '1 minute')
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('market_data.ohlcv_1d',
          start_offset => INTERVAL '2 days',
          end_offset   => INTERVAL '0 days',
          schedule_interval => INTERVAL '1 hour')
        """
    )


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
    if result.scalar() is None:
        return

    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_data.ohlcv_1d CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_data.ohlcv_1m CASCADE")
