"""TCA module wiring — post-trade execution quality analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

from app.modules.tca.core.vwap import VWAPCalculator
from app.modules.tca.repositories import TCARepository
from app.modules.tca.services import TCAService

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    **ctx,
) -> None:
    """Wire TCA module: repo, VWAP calculator, cost engine, service."""
    order_repo = app.state.order_repo
    scorecard_service = app.state.scorecard_service
    market_data_service = app.state.market_data_service

    tca_repo = TCARepository(sf)
    vwap_calculator = VWAPCalculator(market_data_service)
    tca_service = TCAService(
        tca_repo=tca_repo,
        order_repo=order_repo,
        vwap_calculator=vwap_calculator,
        scorecard_service=scorecard_service,
        event_bus=event_bus,
    )

    app.state.tca_service = tca_service

    # Inject into OrderService so filled orders auto-trigger TCA computation
    order_service = app.state.order_service
    order_service._tca_service = tca_service

    import os

    if os.environ.get("APP_ENV", "local") == "local":
        from app.modules.tca.seed import seed_dev_data

        await seed_dev_data(app, sf)
