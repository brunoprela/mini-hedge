"""Seed data for platform — realistic multi-fund hedge fund setup.

Models a prime brokerage hosting three independent funds, each with
dedicated portfolio managers, strategies, and API keys.  Shared admin
staff (compliance, risk) have cross-fund memberships via FGA tuples.

Authorization lives entirely in OpenFGA — there is no fund_memberships table.
Platform operators are seeded with their own identity records + FGA tuples.
"""

from openfga_sdk.client.models import ClientTuple

from app.modules.platform.models import (
    APIKeyRecord,
    FundRecord,
    FundStatus,
    OperatorRecord,
    PortfolioRecord,
    UserRecord,
)
from app.shared.auth import Role, hash_api_key
from app.shared.request_context import ActorType

# ---------------------------------------------------------------------------
# Fixed UUIDs — deterministic for reproducible local development & tests
# ---------------------------------------------------------------------------

# Funds
FUND_ALPHA_ID = "10000000-0000-0000-0000-000000000001"
FUND_BETA_ID = "10000000-0000-0000-0000-000000000002"
FUND_GAMMA_ID = "10000000-0000-0000-0000-000000000003"

# Portfolios — Alpha Capital Partners
PORTFOLIO_ALPHA_EQUITY_LS_ID = "20000000-0000-0000-0000-000000000001"
PORTFOLIO_ALPHA_GLOBAL_MACRO_ID = "20000000-0000-0000-0000-000000000002"

# Portfolios — Bridgewater Systematic
PORTFOLIO_BETA_STAT_ARB_ID = "20000000-0000-0000-0000-000000000010"
PORTFOLIO_BETA_MOMENTUM_ID = "20000000-0000-0000-0000-000000000011"
PORTFOLIO_BETA_MARKET_NEUTRAL_ID = "20000000-0000-0000-0000-000000000012"

# Portfolios — Citrine Event-Driven
PORTFOLIO_GAMMA_EVENT_DRIVEN_ID = "20000000-0000-0000-0000-000000000020"
PORTFOLIO_GAMMA_DISTRESSED_ID = "20000000-0000-0000-0000-000000000021"

# Users
USER_ADMIN_ID = "30000000-0000-0000-0000-000000000001"
USER_ALPHA_PM_ID = "30000000-0000-0000-0000-000000000002"
USER_BETA_PM_ID = "30000000-0000-0000-0000-000000000003"
USER_GAMMA_PM_ID = "30000000-0000-0000-0000-000000000004"
USER_RISK_MANAGER_ID = "30000000-0000-0000-0000-000000000005"
USER_COMPLIANCE_ID = "30000000-0000-0000-0000-000000000006"

# Operators (platform team)
OPERATOR_ADMIN_ID = "50000000-0000-0000-0000-000000000001"
OPERATOR_VIEWER_ID = "50000000-0000-0000-0000-000000000002"

# API Keys
API_KEY_ALPHA_ID = "40000000-0000-0000-0000-000000000001"
API_KEY_BETA_ID = "40000000-0000-0000-0000-000000000002"
API_KEY_GAMMA_ID = "40000000-0000-0000-0000-000000000003"

# Well-known dev API keys — printed on startup, used for local testing
DEV_API_KEY = "mh_dev_00000000000000000000000000000001"
DEV_API_KEY_BETA = "mh_dev_00000000000000000000000000000002"
DEV_API_KEY_GAMMA = "mh_dev_00000000000000000000000000000003"

# Backwards-compatible aliases
DEFAULT_FUND_ID = FUND_ALPHA_ID
PORTFOLIO_EQUITY_LS_ID = PORTFOLIO_ALPHA_EQUITY_LS_ID
PORTFOLIO_GLOBAL_MACRO_ID = PORTFOLIO_ALPHA_GLOBAL_MACRO_ID
DEFAULT_USER_ID = USER_ADMIN_ID
DEFAULT_API_KEY_ID = API_KEY_ALPHA_ID


# ---------------------------------------------------------------------------
# Funds
# ---------------------------------------------------------------------------


def build_seed_funds() -> list[FundRecord]:
    """Three funds representing distinct investment styles."""
    return [
        FundRecord(
            id=FUND_ALPHA_ID,
            slug="alpha",
            name="Alpha Capital Partners",
            status=FundStatus.ACTIVE,
            base_currency="USD",
        ),
        FundRecord(
            id=FUND_BETA_ID,
            slug="beta",
            name="Bridgewater Systematic",
            status=FundStatus.ACTIVE,
            base_currency="USD",
        ),
        FundRecord(
            id=FUND_GAMMA_ID,
            slug="gamma",
            name="Citrine Event-Driven",
            status=FundStatus.ACTIVE,
            base_currency="USD",
        ),
    ]


# ---------------------------------------------------------------------------
# Portfolios
# ---------------------------------------------------------------------------


def build_seed_portfolios() -> list[PortfolioRecord]:
    """Portfolios across all three funds, reflecting realistic strategies."""
    return [
        # Alpha Capital Partners — discretionary equity + macro
        PortfolioRecord(
            id=PORTFOLIO_ALPHA_EQUITY_LS_ID,
            fund_id=FUND_ALPHA_ID,
            slug="equity-long-short",
            name="Equity Long/Short",
            strategy="equity_long_short",
        ),
        PortfolioRecord(
            id=PORTFOLIO_ALPHA_GLOBAL_MACRO_ID,
            fund_id=FUND_ALPHA_ID,
            slug="global-macro",
            name="Global Macro",
            strategy="global_macro",
        ),
        # Bridgewater Systematic — quantitative strategies
        PortfolioRecord(
            id=PORTFOLIO_BETA_STAT_ARB_ID,
            fund_id=FUND_BETA_ID,
            slug="stat-arb",
            name="Statistical Arbitrage",
            strategy="stat_arb",
        ),
        PortfolioRecord(
            id=PORTFOLIO_BETA_MOMENTUM_ID,
            fund_id=FUND_BETA_ID,
            slug="momentum",
            name="Cross-Sectional Momentum",
            strategy="momentum",
        ),
        PortfolioRecord(
            id=PORTFOLIO_BETA_MARKET_NEUTRAL_ID,
            fund_id=FUND_BETA_ID,
            slug="market-neutral",
            name="Market Neutral",
            strategy="market_neutral",
        ),
        # Citrine Event-Driven — event-driven + distressed
        PortfolioRecord(
            id=PORTFOLIO_GAMMA_EVENT_DRIVEN_ID,
            fund_id=FUND_GAMMA_ID,
            slug="event-driven",
            name="Event-Driven",
            strategy="event_driven",
        ),
        PortfolioRecord(
            id=PORTFOLIO_GAMMA_DISTRESSED_ID,
            fund_id=FUND_GAMMA_ID,
            slug="distressed-credit",
            name="Distressed Credit",
            strategy="distressed",
        ),
    ]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def build_seed_users() -> list[UserRecord]:
    """Realistic desk personnel — PMs per fund plus shared compliance/risk."""
    return [
        UserRecord(
            id=USER_ADMIN_ID,
            email="admin@minihedge.dev",
            name="Dev Admin",
            is_active=True,
        ),
        UserRecord(
            id=USER_ALPHA_PM_ID,
            email="james.chen@alphacap.dev",
            name="James Chen",
            is_active=True,
        ),
        UserRecord(
            id=USER_BETA_PM_ID,
            email="sarah.patel@bridgewater.dev",
            name="Sarah Patel",
            is_active=True,
        ),
        UserRecord(
            id=USER_GAMMA_PM_ID,
            email="michael.ross@citrine.dev",
            name="Michael Ross",
            is_active=True,
        ),
        UserRecord(
            id=USER_RISK_MANAGER_ID,
            email="risk@minihedge.dev",
            name="Risk Manager",
            is_active=True,
        ),
        UserRecord(
            id=USER_COMPLIANCE_ID,
            email="compliance@minihedge.dev",
            name="Compliance Officer",
            is_active=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Operators (platform team)
# ---------------------------------------------------------------------------


def build_seed_operators() -> list[OperatorRecord]:
    """Platform operators — ops admin and read-only viewer."""
    return [
        OperatorRecord(
            id=OPERATOR_ADMIN_ID,
            email="ops-admin@minihedge.dev",
            name="Ops Admin",
            is_active=True,
        ),
        OperatorRecord(
            id=OPERATOR_VIEWER_ID,
            email="ops-viewer@minihedge.dev",
            name="Ops Viewer",
            is_active=True,
        ),
    ]


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


def build_seed_api_keys() -> list[APIKeyRecord]:
    """Per-fund API keys for programmatic access (e.g., execution algos, OMS)."""
    return [
        APIKeyRecord(
            id=API_KEY_ALPHA_ID,
            key_hash=hash_api_key(DEV_API_KEY),
            name="Alpha Dev Key",
            actor_type=ActorType.API_KEY,
            fund_id=FUND_ALPHA_ID,
            roles=[Role.ADMIN],
        ),
        APIKeyRecord(
            id=API_KEY_BETA_ID,
            key_hash=hash_api_key(DEV_API_KEY_BETA),
            name="Beta Dev Key",
            actor_type=ActorType.API_KEY,
            fund_id=FUND_BETA_ID,
            roles=[Role.PORTFOLIO_MANAGER],
        ),
        APIKeyRecord(
            id=API_KEY_GAMMA_ID,
            key_hash=hash_api_key(DEV_API_KEY_GAMMA),
            name="Gamma Dev Key",
            actor_type=ActorType.API_KEY,
            fund_id=FUND_GAMMA_ID,
            roles=[Role.PORTFOLIO_MANAGER],
        ),
    ]


# ---------------------------------------------------------------------------
# OpenFGA relationship tuples
# ---------------------------------------------------------------------------


def build_seed_fga_tuples() -> list[ClientTuple]:
    """OpenFGA relationship tuples — single source of truth for all authorization.

    Covers:
    - Platform operator roles (operator → platform:global)
    - Operator fund access (operator → ops_full/ops_read → fund)
    - Fund user roles (user → role → fund)
    - Portfolio → fund parent pointers
    """
    tuples: list[ClientTuple] = []

    # --- Platform operator roles ---
    tuples.append(
        ClientTuple(
            user=f"operator:{OPERATOR_ADMIN_ID}",
            relation="ops_admin",
            object="platform:global",
        )
    )
    tuples.append(
        ClientTuple(
            user=f"operator:{OPERATOR_VIEWER_ID}",
            relation="ops_viewer",
            object="platform:global",
        )
    )

    # --- Operator fund access ---
    # ops_admin gets ops_full on all funds
    for fund_id in [FUND_ALPHA_ID, FUND_BETA_ID, FUND_GAMMA_ID]:
        tuples.append(
            ClientTuple(
                user=f"operator:{OPERATOR_ADMIN_ID}",
                relation="ops_full",
                object=f"fund:{fund_id}",
            )
        )

    # ops_viewer gets ops_read on all funds
    for fund_id in [FUND_ALPHA_ID, FUND_BETA_ID, FUND_GAMMA_ID]:
        tuples.append(
            ClientTuple(
                user=f"operator:{OPERATOR_VIEWER_ID}",
                relation="ops_read",
                object=f"fund:{fund_id}",
            )
        )

    # --- Fund user roles (replaces fund_memberships table) ---

    # Admin — full access to Alpha
    tuples.append(
        ClientTuple(
            user=f"user:{USER_ADMIN_ID}",
            relation="admin",
            object=f"fund:{FUND_ALPHA_ID}",
        )
    )

    # PMs per fund
    for user_id, fund_id in [
        (USER_ALPHA_PM_ID, FUND_ALPHA_ID),
        (USER_BETA_PM_ID, FUND_BETA_ID),
        (USER_GAMMA_PM_ID, FUND_GAMMA_ID),
    ]:
        tuples.append(
            ClientTuple(
                user=f"user:{user_id}",
                relation="portfolio_manager",
                object=f"fund:{fund_id}",
            )
        )

    # Risk manager — risk_manager on all funds
    for fund_id in [FUND_ALPHA_ID, FUND_BETA_ID, FUND_GAMMA_ID]:
        tuples.append(
            ClientTuple(
                user=f"user:{USER_RISK_MANAGER_ID}",
                relation="risk_manager",
                object=f"fund:{fund_id}",
            )
        )

    # Compliance — compliance on all funds
    for fund_id in [FUND_ALPHA_ID, FUND_BETA_ID, FUND_GAMMA_ID]:
        tuples.append(
            ClientTuple(
                user=f"user:{USER_COMPLIANCE_ID}",
                relation="compliance",
                object=f"fund:{fund_id}",
            )
        )

    # --- Portfolio → fund parent pointers ---
    portfolio_fund_map = {
        PORTFOLIO_ALPHA_EQUITY_LS_ID: FUND_ALPHA_ID,
        PORTFOLIO_ALPHA_GLOBAL_MACRO_ID: FUND_ALPHA_ID,
        PORTFOLIO_BETA_STAT_ARB_ID: FUND_BETA_ID,
        PORTFOLIO_BETA_MOMENTUM_ID: FUND_BETA_ID,
        PORTFOLIO_BETA_MARKET_NEUTRAL_ID: FUND_BETA_ID,
        PORTFOLIO_GAMMA_EVENT_DRIVEN_ID: FUND_GAMMA_ID,
        PORTFOLIO_GAMMA_DISTRESSED_ID: FUND_GAMMA_ID,
    }
    for portfolio_id, fund_id in portfolio_fund_map.items():
        tuples.append(
            ClientTuple(
                user=f"fund:{fund_id}",
                relation="fund",
                object=f"portfolio:{portfolio_id}",
            )
        )

    return tuples
