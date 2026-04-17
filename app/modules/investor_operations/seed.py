"""Seed data for investor operations -- fund terms."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.investor_operations.services import InvestorKYCService
    from app.modules.platform.repositories import FundRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for investor operations."""
    from app.modules.investor_operations.repositories.fund_terms import FundTermsRepository

    service: InvestorKYCService = app.state.kyc_service
    terms_repo = FundTermsRepository(sf)

    fund_repo: FundRepository = app.state.fund_repo
    active_funds = await fund_repo.list_active()
    for fund in active_funds:
        async with sf.fund_scope(fund.slug), sf() as session:
            existing = await terms_repo.list_active(session=session)
            if not existing:
                await service.upsert_fund_terms(
                    share_class="default",
                    lock_up_months=12,
                    notice_period_days=45,
                    redemption_frequency="quarterly",
                    gate_pct=Decimal("0.25"),
                    minimum_subscription=Decimal("1000000"),
                    minimum_redemption=Decimal("100000"),
                    dealing_day=-1,
                    payment_days=30,
                    session=session,
                )
                await session.commit()
                logger.info(
                    "fund_terms_seeded",
                    fund=fund.slug,
                    share_class="default",
                )
