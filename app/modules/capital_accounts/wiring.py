"""Capital accounts module wiring — repos, service."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> None:
    """Wire capital accounts module: repos, service."""
    from app.modules.capital_accounts.repositories.account import CapitalAccountRepository
    from app.modules.platform.repositories.investor import InvestorRepository
    from app.modules.capital_accounts.repositories.transaction import (
        CapitalTransactionRepository,
    )
    from app.modules.capital_accounts.services import (
        CapitalAccountService,
        CapitalTransactionService,
    )

    investor_repo = InvestorRepository(sf)
    account_repo = CapitalAccountRepository(sf)
    transaction_repo = CapitalTransactionRepository(sf)

    capital_service = CapitalAccountService(
        investor_repo=investor_repo,
        account_repo=account_repo,
        transaction_repo=transaction_repo,
    )

    # Wire cash service for subscription/redemption cash flows
    cash_service = getattr(app.state, "cash_service", None)

    capital_transaction_service = CapitalTransactionService(
        account_repo=account_repo,
        transaction_repo=transaction_repo,
        cash_service=cash_service,
        event_bus=event_bus,
    )

    app.state.capital_account_service = capital_service
    app.state.capital_transaction_service = capital_transaction_service
    app.state.investor_repo = investor_repo

    # Seed investors + initial subscriptions in local environment
    if os.environ.get("APP_ENV", "local") == "local":
        from app.modules.capital_accounts.seed import seed_dev_data

        await seed_dev_data(app, sf)

    logger.info("capital_accounts_module_ready")
