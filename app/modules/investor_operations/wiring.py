"""Investor operations module wiring — repos, KYC adapter, service."""

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
    """Wire investor operations module: repos, KYC adapter, service."""
    from app.adapters.factory import build_kyc_screening_adapter
    from app.modules.investor_operations.repository import (
        FundTermsRepository,
        InvestorKYCRepository,
        RedemptionRequestRepository,
        SubscriptionRequestRepository,
    )
    from app.modules.investor_operations.service import InvestorOperationsService

    sub_repo = SubscriptionRequestRepository(sf)
    red_repo = RedemptionRequestRepository(sf)
    terms_repo = FundTermsRepository(sf)
    kyc_repo = InvestorKYCRepository(sf)

    kyc_adapter = build_kyc_screening_adapter(settings)
    capital_service = app.state.capital_account_service

    service = InvestorOperationsService(
        subscription_repo=sub_repo,
        redemption_repo=red_repo,
        fund_terms_repo=terms_repo,
        kyc_repo=kyc_repo,
        capital_service=capital_service,
        kyc_adapter=kyc_adapter,
        event_bus=event_bus,
    )
    app.state.investor_ops_service = service

    # Seed fund terms in local environment
    if os.environ.get("APP_ENV", "local") == "local":
        from app.modules.investor_operations.seed import seed_dev_data

        await seed_dev_data(app, sf)

    logger.info("investor_operations_module_ready")
