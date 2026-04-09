"""Alternative data module wiring — providers, repo, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.alt_data.repositories import AltDataFeedRepository, AltDataPointRepository
from app.modules.alt_data.services import AltDataService

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.adapters.alt_data import AltDataProvider
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
    """Wire alternative data module."""
    alt_data_provider: AltDataProvider | None = ctx.get("alt_data_provider")

    feed_repo = AltDataFeedRepository(sf)
    point_repo = AltDataPointRepository(sf)

    providers: list[AltDataProvider] = []
    if alt_data_provider is not None:
        providers.append(alt_data_provider)

    svc = AltDataService(
        feed_repo=feed_repo,
        point_repo=point_repo,
        providers=providers,
        session_factory=sf,
        event_bus=event_bus,
    )
    app.state.alt_data_service = svc
    logger.info("alt_data_module_ready")
