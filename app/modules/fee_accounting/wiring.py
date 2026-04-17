"""Fee accounting module wiring — repos, service."""

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
    """Wire fee accounting module: repos, service."""
    from app.modules.fee_accounting.repositories.fee_accrual import FeeAccrualRepository
    from app.modules.fee_accounting.repositories.fee_schedule import FeeScheduleRepository
    from app.modules.fee_accounting.repositories.high_water_mark import HighWaterMarkRepository
    from app.modules.fee_accounting.services import FeeAccountingService

    schedule_repo = FeeScheduleRepository(sf)
    accrual_repo = FeeAccrualRepository(sf)
    hwm_repo = HighWaterMarkRepository(sf)

    fee_service = FeeAccountingService(
        session_factory=sf,
        schedule_repo=schedule_repo,
        accrual_repo=accrual_repo,
        hwm_repo=hwm_repo,
        event_bus=event_bus,
    )
    app.state.fee_accounting_service = fee_service
    app.state.fee_schedule_repo = schedule_repo
    app.state.fee_accrual_repo = accrual_repo

    # Seed fee schedules in local environment
    if os.environ.get("APP_ENV", "local") == "local":
        from app.modules.fee_accounting.seed import seed_dev_data

        await seed_dev_data(app, sf)

    logger.info("fee_accounting_module_ready")
