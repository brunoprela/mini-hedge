"""Add immutability triggers to audit_log table.

Prevents UPDATE and DELETE operations on the audit_log table at the
database level. This is defense-in-depth — the application role should
also lack UPDATE/DELETE grants, but the trigger catches any bypass
(direct SQL, superuser, migration accidents).

Revision ID: 008
Revises: 007
Create Date: 2026-04-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008"
down_revision: str = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION platform.audit_log_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is immutable: % operations are not permitted', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

CREATE_TRIGGER_UPDATE = """
CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON platform.audit_log
    FOR EACH ROW
    EXECUTE FUNCTION platform.audit_log_immutable();
"""

CREATE_TRIGGER_DELETE = """
CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON platform.audit_log
    FOR EACH ROW
    EXECUTE FUNCTION platform.audit_log_immutable();
"""

CREATE_TRIGGER_TRUNCATE = """
CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON platform.audit_log
    FOR EACH STATEMENT
    EXECUTE FUNCTION platform.audit_log_immutable();
"""


def upgrade() -> None:
    op.execute(TRIGGER_FUNCTION)
    op.execute(CREATE_TRIGGER_UPDATE)
    op.execute(CREATE_TRIGGER_DELETE)
    op.execute(CREATE_TRIGGER_TRUNCATE)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_truncate ON platform.audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON platform.audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON platform.audit_log;")
    op.execute("DROP FUNCTION IF EXISTS platform.audit_log_immutable();")
