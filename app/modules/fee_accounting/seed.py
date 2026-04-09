"""Seed data for fee accounting -- fee schedules per fund."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.fee_accounting.repositories.fee_schedule import FeeScheduleRepository
    from app.modules.platform.repositories import FundRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for fee accounting."""
    from app.modules.fee_accounting.models.fee_schedule import FeeScheduleRecord

    schedule_repo: FeeScheduleRepository = app.state.fee_schedule_repo
    fund_repo: FundRepository = app.state.fund_repo
    active_funds = await fund_repo.get_all_active()

    # Realistic hedge fund fee structures
    fund_fee_configs = {
        "alpha": (200, Decimal("0.20"), Decimal("0.08"), True, "annual", "quarterly"),
        "beta": (150, Decimal("0.15"), Decimal("0.06"), True, "quarterly", "quarterly"),
        "gamma": (175, Decimal("0.20"), Decimal("0.07"), True, "annual", "semi-annual"),
    }
    for fund in active_funds:
        config = fund_fee_configs.get(
            fund.slug,
            (200, Decimal("0.20"), Decimal("0.08"), True, "annual", "quarterly"),
        )
        async with sf.fund_scope(fund.slug), sf() as session:
            existing = await schedule_repo.get_by_fund_slug(fund.slug, session=session)
            if existing is None:
                # Default class (standard 2/20)
                await schedule_repo.upsert(
                    FeeScheduleRecord(
                        fund_slug=fund.slug,
                        share_class="default",
                        management_fee_bps=config[0],
                        performance_fee_pct=config[1],
                        hurdle_rate_pct=config[2],
                        high_water_mark=config[3],
                        crystallization_frequency=config[4],
                        payment_frequency=config[5],
                    ),
                    session=session,
                )
                # Founders class (reduced fees -- 1/10)
                await schedule_repo.upsert(
                    FeeScheduleRecord(
                        fund_slug=fund.slug,
                        share_class="founders",
                        management_fee_bps=100,
                        performance_fee_pct=Decimal("0.10"),
                        hurdle_rate_pct=config[2],
                        high_water_mark=config[3],
                        crystallization_frequency=config[4],
                        payment_frequency=config[5],
                    ),
                    session=session,
                )
    logger.info("fee_schedules_seeded", fund_count=len(active_funds))
