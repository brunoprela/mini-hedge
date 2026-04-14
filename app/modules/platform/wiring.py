"""Platform module wiring — repos, auth, admin, FGA."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.config import Settings
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus
    from app.shared.fga import FGAClient

from app.modules.platform.repositories import (
    APIKeyRepository,
    AuditLogRepository,
    CustomerRepository,
    FundRepository,
    OperatorRepository,
    PortfolioRepository,
    UserRepository,
)
from app.modules.platform.seed import (
    DEV_API_KEY,
    build_seed_api_keys,
    build_seed_customers,
    build_seed_funds,
    build_seed_operators,
    build_seed_users,
)
from app.modules.platform.services import AdminService, AuthService
from app.shared.auth.jwt import configure_customer_realms

logger = structlog.get_logger()


def _is_local_env() -> bool:
    return os.environ.get("APP_ENV", "local") == "local"


async def _seed_platform(
    customer_repo: CustomerRepository,
    fund_repo: FundRepository,
    portfolio_repo: PortfolioRepository,
    user_repo: UserRepository,
    operator_repo: OperatorRepository,
    api_key_repo: APIKeyRepository,
) -> None:
    """Seed customers, funds, users, operators, and API keys.

    Portfolios and compliance rules are NOT seeded here — they are created
    via the UI, API, or ``make seed``.  This keeps startup minimal: only
    the data needed for authentication and fund discovery.
    """
    # Customers must be seeded before funds/users (FK dependency)
    existing_customers = await customer_repo.get_all_active()
    if not existing_customers:
        customers = build_seed_customers()
        for customer in customers:
            await customer_repo.insert(customer)
        logger.info("customers_seeded", count=len(customers))

    existing_funds = await fund_repo.get_all_active()
    if not existing_funds:
        funds = build_seed_funds()
        for fund in funds:
            await fund_repo.insert(fund)
        logger.info("funds_seeded", count=len(funds))

    existing_users = await user_repo.get_all_active()
    if not existing_users:
        users = build_seed_users()
        for user in users:
            await user_repo.insert(user)
        api_keys = build_seed_api_keys()
        for api_key in api_keys:
            await api_key_repo.insert(api_key)
        logger.info(
            "auth_seeded",
            users=len(users),
            api_keys=len(api_keys),
        )

    # Seed operators
    existing_operators = await operator_repo.get_all_active()
    if not existing_operators:
        operators = build_seed_operators()
        for op in operators:
            await operator_repo.insert(op)
        logger.info("operators_seeded", count=len(operators))


async def setup_fga(app: FastAPI, settings: Settings) -> FGAClient | None:
    """Initialize OpenFGA if enabled. Returns the FGA client or None."""
    if not settings.fga_enabled:
        return None

    import importlib

    importlib.import_module("app.shared.fga.resources")  # triggers resource type registration
    from app.modules.platform.seed import build_seed_fga_tuples
    from app.shared.fga.startup import initialize_fga

    fga_client = await initialize_fga(
        api_url=settings.fga_api_url,
        store_name=settings.fga_store_name,
    )
    app.state.fga = fga_client
    tuples = build_seed_fga_tuples()
    await fga_client.write_tuples(tuples)
    logger.info("fga_tuples_seeded", count=len(tuples))
    return fga_client


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings: Settings | None = None,
    fga_client: FGAClient | None = None,
    engine: AsyncEngine | None = None,
    **ctx,
) -> tuple[AuthService, FundRepository]:
    """Wire platform module: repos, auth service.  Dev seeding is in seed_dev_data()."""
    customer_repo = CustomerRepository(sf)
    fund_repo = FundRepository(sf)
    portfolio_repo = PortfolioRepository(sf)
    user_repo = UserRepository(sf)
    operator_repo = OperatorRepository(sf)
    api_key_repo = APIKeyRepository(sf)

    # Dev seeding — only populates data in local environment
    if _is_local_env():
        await _seed_platform(
            customer_repo, fund_repo, portfolio_repo, user_repo, operator_repo, api_key_repo
        )

    # Load per-customer Keycloak realm mapping
    import json

    _raw_realms = getattr(settings, "keycloak_customer_realms", "{}")
    try:
        _realm_map = json.loads(_raw_realms) if isinstance(_raw_realms, str) else _raw_realms
    except (json.JSONDecodeError, TypeError):
        _realm_map = {}
    if _realm_map:
        configure_customer_realms(_realm_map)
        logger.info("customer_realms_configured", count=len(_realm_map))

    auth_service = AuthService(
        user_repo=user_repo,
        fund_repo=fund_repo,
        operator_repo=operator_repo,
        api_key_repo=api_key_repo,
        fga_client=fga_client,
        customer_repo=customer_repo,
        jwt_secret=settings.jwt_secret,
        jwt_algorithm=settings.jwt_algorithm,
        jwt_expiry_minutes=settings.jwt_expiry_minutes,
        keycloak_url=settings.keycloak_url,
        keycloak_browser_url=settings.keycloak_browser_url,
        keycloak_realm=settings.keycloak_realm,
        keycloak_client_id=settings.keycloak_client_id,
        keycloak_ops_realm=settings.keycloak_ops_realm,
        keycloak_ops_client_id=settings.keycloak_ops_client_id,
        keycloak_investors_realm=settings.keycloak_investors_realm,
        keycloak_investors_client_id=settings.keycloak_investors_client_id,
    )
    app.state.auth_service = auth_service
    app.state.api_key_repo = api_key_repo
    app.state.customer_repo = customer_repo
    app.state.fund_repo = fund_repo
    app.state.portfolio_repo = portfolio_repo
    app.state.operator_repo = operator_repo

    audit_repo = AuditLogRepository(sf)
    app.state.audit_repo = audit_repo

    from app.modules.platform.core.audit_verifier import AuditIntegrityVerifier

    app.state.audit_verifier = AuditIntegrityVerifier(sf)

    # Admin service (only if FGA is available)
    if fga_client is not None:
        admin_service = AdminService(
            user_repo=user_repo,
            operator_repo=operator_repo,
            fund_repo=fund_repo,
            customer_repo=customer_repo,
            fga_client=fga_client,
            audit_repo=audit_repo,
            engine=engine,
            event_bus=event_bus,
            auth_service=auth_service,
        )
        app.state.admin_service = admin_service

    return auth_service, fund_repo
