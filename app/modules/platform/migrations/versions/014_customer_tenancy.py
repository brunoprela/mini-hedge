"""Customer tenancy — customers, servicing_edges, and customer_id FKs.

Introduces the customer layer between cell and fund:
- customers table (direct_fund / fund_administrator)
- servicing_edges table (delegated access links)
- customer_id FK on funds and users

See ADR 0010 and ADR 0011.

Revision ID: 014
Revises: 013
Create Date: 2026-04-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PG_UUID = sa.dialects.postgresql.UUID
SCHEMA = "platform"


def upgrade() -> None:
    # -- customers --
    op.create_table(
        "customers",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "customer_type",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'direct_fund'"),
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("offboarded_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_platform_customers_slug", "customers", ["slug"], unique=True, schema=SCHEMA
    )
    op.create_index(
        "ix_platform_customers_type", "customers", ["customer_type"], schema=SCHEMA
    )

    # -- servicing_edges --
    op.create_table(
        "servicing_edges",
        sa.Column("id", PG_UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column(
            "admin_customer_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.customers.id"),
            nullable=False,
        ),
        sa.Column(
            "client_customer_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.customers.id"),
            nullable=False,
        ),
        sa.Column(
            "scoped_roles",
            sa.dialects.postgresql.ARRAY(sa.String(64)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_platform_servicing_edges_admin_client",
        "servicing_edges",
        ["admin_customer_id", "client_customer_id"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_platform_servicing_edges_client",
        "servicing_edges",
        ["client_customer_id"],
        schema=SCHEMA,
    )

    # -- Add customer_id FK to funds (nullable for backfill, then NOT NULL) --
    op.add_column(
        "funds",
        sa.Column(
            "customer_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.customers.id"),
            nullable=True,
        ),
        schema=SCHEMA,
    )

    # -- Add customer_id FK to users (nullable for backfill, then NOT NULL) --
    op.add_column(
        "users",
        sa.Column(
            "customer_id",
            PG_UUID(),
            sa.ForeignKey(f"{SCHEMA}.customers.id"),
            nullable=True,
        ),
        schema=SCHEMA,
    )

    # Backfill will happen via seed / application logic, then a follow-up
    # migration makes the columns NOT NULL. For greenfield (dev/test), the
    # seed inserts customers first so the FK is always populated.


def downgrade() -> None:
    op.drop_column("users", "customer_id", schema=SCHEMA)
    op.drop_column("funds", "customer_id", schema=SCHEMA)
    op.drop_table("servicing_edges", schema=SCHEMA)
    op.drop_table("customers", schema=SCHEMA)
