"""Enable Row-Level Security on platform tables with fund_id.

Adds RLS policies to portfolios, fund_memberships, and api_keys.
These tables already have fund_id columns — no schema changes needed.

Revision ID: 004
Revises: 003
Create Date: 2026-04-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- platform.portfolios ---
    op.execute("ALTER TABLE platform.portfolios ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform.portfolios FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON platform.portfolios
            USING (
                current_setting('app.current_fund_id', true) = 'BYPASS'
                OR fund_id = current_setting('app.current_fund_id', true)::uuid
            )
        """
    )

    # --- platform.fund_memberships ---
    op.execute("ALTER TABLE platform.fund_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform.fund_memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON platform.fund_memberships
            USING (
                current_setting('app.current_fund_id', true) = 'BYPASS'
                OR fund_id = current_setting('app.current_fund_id', true)::uuid
            )
        """
    )

    # --- platform.api_keys ---
    op.execute("ALTER TABLE platform.api_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform.api_keys FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON platform.api_keys
            USING (
                current_setting('app.current_fund_id', true) = 'BYPASS'
                OR fund_id = current_setting('app.current_fund_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    for table in ("api_keys", "fund_memberships", "portfolios"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON platform.{table}")
        op.execute(f"ALTER TABLE platform.{table} DISABLE ROW LEVEL SECURITY")
