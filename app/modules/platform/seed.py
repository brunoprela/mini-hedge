"""Seed data for platform — default fund, portfolios, user, API key, and FGA tuples."""

from openfga_sdk.client.models import ClientTuple

from app.modules.platform.models import (
    APIKeyRecord,
    FundMembershipRecord,
    FundRecord,
    FundStatus,
    PortfolioRecord,
    UserRecord,
)
from app.shared.auth import Role, hash_api_key
from app.shared.request_context import ActorType

# Fixed UUIDs for reproducible local development
DEFAULT_FUND_ID = "10000000-0000-0000-0000-000000000001"
PORTFOLIO_EQUITY_LS_ID = "20000000-0000-0000-0000-000000000001"
PORTFOLIO_GLOBAL_MACRO_ID = "20000000-0000-0000-0000-000000000002"
DEFAULT_USER_ID = "30000000-0000-0000-0000-000000000001"
DEFAULT_API_KEY_ID = "40000000-0000-0000-0000-000000000001"

# Well-known dev API key — printed on startup, used for local testing
DEV_API_KEY = "mh_dev_00000000000000000000000000000001"


def build_seed_fund() -> FundRecord:
    return FundRecord(
        id=DEFAULT_FUND_ID,
        slug="fund-alpha",
        name="Alpha Capital Partners",
        status=FundStatus.ACTIVE,
        base_currency="USD",
    )


def build_seed_portfolios() -> list[PortfolioRecord]:
    return [
        PortfolioRecord(
            id=PORTFOLIO_EQUITY_LS_ID,
            fund_id=DEFAULT_FUND_ID,
            slug="equity-long-short",
            name="Equity Long/Short",
            strategy="equity_long_short",
        ),
        PortfolioRecord(
            id=PORTFOLIO_GLOBAL_MACRO_ID,
            fund_id=DEFAULT_FUND_ID,
            slug="global-macro",
            name="Global Macro",
            strategy="global_macro",
        ),
    ]


def build_seed_user() -> UserRecord:
    return UserRecord(
        id=DEFAULT_USER_ID,
        email="admin@minihedge.dev",
        name="Dev Admin",
        is_active=True,
    )


def build_seed_membership() -> FundMembershipRecord:
    return FundMembershipRecord(
        user_id=DEFAULT_USER_ID,
        fund_id=DEFAULT_FUND_ID,
        role=Role.ADMIN,
    )


def build_seed_api_key() -> APIKeyRecord:
    return APIKeyRecord(
        id=DEFAULT_API_KEY_ID,
        key_hash=hash_api_key(DEV_API_KEY),
        name="Dev API Key",
        actor_type=ActorType.API_KEY,
        fund_id=DEFAULT_FUND_ID,
        roles=[Role.ADMIN],
    )


def build_seed_fga_tuples() -> list[ClientTuple]:
    """Build OpenFGA relationship tuples matching the seed data.

    The admin user is a fund admin, which inherits full access to all portfolios.
    Each portfolio gets a parent pointer to its fund.
    """
    return [
        # Admin user is fund admin
        ClientTuple(
            user=f"user:{DEFAULT_USER_ID}",
            relation="admin",
            object=f"fund:{DEFAULT_FUND_ID}",
        ),
        # Portfolio -> fund parent pointers
        ClientTuple(
            user=f"fund:{DEFAULT_FUND_ID}",
            relation="fund",
            object=f"portfolio:{PORTFOLIO_EQUITY_LS_ID}",
        ),
        ClientTuple(
            user=f"fund:{DEFAULT_FUND_ID}",
            relation="fund",
            object=f"portfolio:{PORTFOLIO_GLOBAL_MACRO_ID}",
        ),
    ]
