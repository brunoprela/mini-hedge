"""Attribution module wiring — repos, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.attribution.repositories import (
    BrinsonFachlerRepository,
    BrinsonFachlerSectorRepository,
    CumulativeAttributionRepository,
    RiskBasedRepository,
    RiskFactorContributionRepository,
)
from app.modules.attribution.services import AttributionService

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.market_data.services import MarketDataService
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
    """Wire attribution module: repos, service."""
    bf_repo = BrinsonFachlerRepository(sf)
    bf_sector_repo = BrinsonFachlerSectorRepository(sf)
    rb_repo = RiskBasedRepository(sf)
    rfc_repo = RiskFactorContributionRepository(sf)
    cum_repo = CumulativeAttributionRepository(sf)

    position_service = app.state.position_service
    sm_service = app.state.security_master_service
    market_data_service: MarketDataService = app.state.market_data_service
    attribution_service = AttributionService(
        bf_repo=bf_repo,
        bf_sector_repo=bf_sector_repo,
        rb_repo=rb_repo,
        rfc_repo=rfc_repo,
        cum_repo=cum_repo,
        position_service=position_service,
        security_master_service=sm_service,
        fx_converter=market_data_service.fx_converter,
        event_bus=event_bus,
    )
    app.state.attribution_service = attribution_service
