"""Seed data for regulatory — sample filings and performance letters."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository
    from app.modules.regulatory.services import RegulatoryService
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for regulatory filings."""
    svc: RegulatoryService = app.state.regulatory_service
    fund_repo: FundRepository = app.state.fund_repo
    active_funds = await fund_repo.list_active()

    for fund in active_funds:
        async with sf.fund_scope(fund.slug), sf() as session:
            # Check if filings already exist
            existing = await svc.list_filings(session=session)
            if existing:
                continue

            # Generate sample Form PF for Q1 2026
            await svc.generate_form_pf(
                fund.slug,
                date(2026, 3, 31),
                fund_name=fund.name,
                session=session,
            )

            # Generate sample performance letter for March 2026
            await svc.generate_performance_letter(
                fund.slug,
                date(2026, 3, 31),
                fund_name=fund.name,
                session=session,
            )

            logger.info("regulatory_filings_seeded", fund=fund.slug)

    logger.info("regulatory_seed_complete")
