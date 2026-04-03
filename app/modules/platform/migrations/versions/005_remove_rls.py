"""Remove RLS from platform tables.

Tenant isolation is now handled by per-fund PostgreSQL schemas for position
data.  Platform tables (portfolios, memberships, api_keys) are shared and
filtered by the application layer (auth + FGA).  RLS is no longer needed
since the session factory no longer sets app.current_fund_id.

Revision ID: 005
Revises: 004
Create Date: 2026-04-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("api_keys", "fund_memberships", "portfolios"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON platform.{table}")
        op.execute(f"ALTER TABLE platform.{table} DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in ("portfolios", "fund_memberships", "api_keys"):
        op.execute(f"ALTER TABLE platform.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE platform.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON platform.{table}
                USING (
                    current_setting('app.current_fund_id', true) = 'BYPASS'
                    OR fund_id = current_setting('app.current_fund_id', true)::uuid
                )
            """
        )
