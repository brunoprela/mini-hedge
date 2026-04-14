"""Seed data for cash management — initial balances per portfolio."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.cash_management.interfaces import CashFlowType

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository, PortfolioRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# Initial cash balances per currency for each portfolio.
# USD balances are seeded by app/seed.py with fund-specific amounts;
# this module seeds only non-USD currencies.
_INITIAL_BALANCES: list[tuple[str, Decimal, str]] = [
    ("EUR", Decimal("2000000"), "Initial EUR cash allocation"),
    ("GBP", Decimal("1500000"), "Initial GBP cash allocation"),
]


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for cash balances."""
    cash_service = getattr(app.state, "cash_service", None)
    if cash_service is None:
        logger.debug("cash_management_seed_skipped", reason="service not available")
        return

    fund_repo: FundRepository = app.state.fund_repo
    portfolio_repo: PortfolioRepository = app.state.portfolio_repo
    active_funds = await fund_repo.get_all_active()

    seeded = 0
    for fund in active_funds:
        async with sf.fund_scope(fund.slug):
            portfolios = await portfolio_repo.get_by_fund(fund.id)
            for portfolio in portfolios:
                pid = UUID(portfolio.id)
                existing = await cash_service.get_balances(pid)
                if existing:
                    continue

                for currency, amount, desc in _INITIAL_BALANCES:
                    await cash_service.credit(
                        pid,
                        currency,
                        amount,
                        CashFlowType.SUBSCRIPTION,
                        description=desc,
                    )
                seeded += 1

    if seeded:
        logger.info("cash_management_seed_complete", portfolios_seeded=seeded)
    else:
        logger.debug("cash_management_seed_skipped", reason="balances already exist")
