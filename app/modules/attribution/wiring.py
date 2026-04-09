"""Attribution module wiring — repo, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.attribution.repository import AttributionRepository
from app.modules.attribution.service import AttributionService

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.market_data.service import MarketDataService
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
    """Wire attribution module: repo, service."""
    attribution_repo = AttributionRepository(sf)
    position_service = app.state.position_service
    sm_service = app.state.security_master_service
    market_data_service: MarketDataService = app.state.market_data_service
    attribution_service = AttributionService(
        attribution_repo=attribution_repo,
        position_service=position_service,
        security_master_service=sm_service,
        fx_converter=market_data_service.fx_converter,
    )
    app.state.attribution_service = attribution_service
