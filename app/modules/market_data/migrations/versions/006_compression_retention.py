"""TimescaleDB compression and retention policies for prices hypertable.

- Compression: after 7 days, compress chunks to reduce storage
- Retention: drop chunks older than 2 years

Both policies are no-ops if TimescaleDB is not installed (standard PostgreSQL).

Revision ID: 006
Revises: 005
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "006"
down_revision: str = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable compression on prices hypertable (7-day lag)
    op.execute("""
        DO $$
        BEGIN
            -- Only run if TimescaleDB is available
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                ALTER TABLE market_data.prices SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'instrument_id',
                    timescaledb.compress_orderby = 'timestamp DESC'
                );
                PERFORM add_compression_policy('market_data.prices', INTERVAL '7 days');
                PERFORM add_retention_policy('market_data.prices', INTERVAL '2 years');
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM remove_retention_policy('market_data.prices', if_exists => true);
                PERFORM remove_compression_policy('market_data.prices', if_exists => true);
                ALTER TABLE market_data.prices SET (timescaledb.compress = false);
            END IF;
        END
        $$;
    """)
