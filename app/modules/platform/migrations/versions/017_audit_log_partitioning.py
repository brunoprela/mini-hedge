"""Monthly partitioning support for audit_log table.

Installs a helper function ``create_audit_partition(date)`` that creates
monthly partitions for the ``audit_log`` table. The function is safe to
call on both partitioned and non-partitioned tables — it checks whether
the table is partitioned before attempting to create a child partition.

The actual conversion from a regular table to a partitioned table is a
production ops task (requires pg_partman or a manual copy). Once the table
is partitioned, call this function monthly (via pg_cron or similar) to
create upcoming partitions.

Revision ID: 017
Revises: 016
Create Date: 2026-04-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "017"
down_revision: str = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"


def upgrade() -> None:
    # Install a helper function to create monthly partitions.
    # Safe to call even when audit_log is not yet partitioned —
    # it checks pg_class.relkind before creating child tables.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.create_audit_partition(
            partition_date DATE
        ) RETURNS void AS $$
        DECLARE
            start_date DATE;
            end_date DATE;
            tbl_kind CHAR;
        BEGIN
            -- Only proceed if audit_log is a partitioned table (relkind = 'p')
            SELECT relkind INTO tbl_kind
            FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname = '{SCHEMA}' AND c.relname = 'audit_log';

            IF tbl_kind IS DISTINCT FROM 'p' THEN
                RETURN;  -- table is not partitioned yet; skip
            END IF;

            start_date := date_trunc('month', partition_date);
            end_date := start_date + INTERVAL '1 month';

            -- Skip if partition already exists
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = '{SCHEMA}'
                  AND tablename = 'audit_log_' || to_char(start_date, 'YYYY_MM')
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I.%I PARTITION OF %I.audit_log '
                    'FOR VALUES FROM (%L) TO (%L)',
                    '{SCHEMA}',
                    'audit_log_' || to_char(start_date, 'YYYY_MM'),
                    '{SCHEMA}',
                    start_date::text,
                    end_date::text
                );
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.create_audit_partition(DATE);")
