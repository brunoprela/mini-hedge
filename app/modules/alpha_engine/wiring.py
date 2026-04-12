"""Alpha engine module wiring — repos, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.alpha_engine.repositories import (
    OptimizationRunRepository,
    OptimizationWeightRepository,
    OrderIntentRepository,
    ScenarioRunRepository,
)
from app.modules.alpha_engine.services import AlphaService

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> None:
    """Wire alpha engine module: repos, service."""
    scenario_repo = ScenarioRunRepository(sf)
    opt_run_repo = OptimizationRunRepository(sf)
    opt_weight_repo = OptimizationWeightRepository(sf)
    intent_repo = OrderIntentRepository(sf)

    position_service = app.state.position_service
    sm_service = app.state.security_master_service
    alpha_service = AlphaService(
        scenario_repo=scenario_repo,
        opt_run_repo=opt_run_repo,
        opt_weight_repo=opt_weight_repo,
        intent_repo=intent_repo,
        position_service=position_service,
        security_master_service=sm_service,
        event_bus=event_bus,
    )
    app.state.alpha_service = alpha_service

    import os

    if os.environ.get("APP_ENV", "local") == "local":
        try:
            from app.modules.alpha_engine.seed import seed_dev_data

            await seed_dev_data(app, sf)
        except Exception:
            pass
