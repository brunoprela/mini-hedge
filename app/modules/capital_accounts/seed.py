"""Seed data for capital accounts -- investors and initial subscriptions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.platform.seed import (
    SEED_SUBSCRIPTIONS,
    build_seed_investors,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.capital_accounts.service import CapitalAccountService
    from app.modules.platform.fund_repository import FundRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for capital accounts."""
    from app.modules.capital_accounts.repository import (
        CapitalAccountRepository,
        InvestorRepository,
    )

    investor_repo: InvestorRepository = app.state.investor_repo
    capital_service: CapitalAccountService = app.state.capital_account_service
    account_repo = CapitalAccountRepository(sf)

    # Seed investors (platform-scoped)
    existing = await investor_repo.get_all_active()
    if not existing:
        investors = build_seed_investors()
        await investor_repo.insert_batch(investors)
        logger.info("investors_seeded", count=len(investors))

    # Seed initial subscriptions per fund (capital accounts are fund-scoped)
    fund_repo: FundRepository = app.state.fund_repo
    active_funds = await fund_repo.get_all_active()
    for fund in active_funds:
        async with sf.fund_scope(fund.slug), sf() as session:
            existing_accounts = await account_repo.get_latest_by_fund(
                session=session,
            )
            if not existing_accounts:
                for inv_id, amount, nav in SEED_SUBSCRIPTIONS:
                    await capital_service.process_subscription(
                        investor_id=inv_id,
                        amount=Decimal(amount),
                        nav_per_share=Decimal(nav),
                        business_date=date.today(),
                        session=session,
                    )
                logger.info(
                    "capital_subscriptions_seeded",
                    fund=fund.slug,
                    count=len(SEED_SUBSCRIPTIONS),
                )
