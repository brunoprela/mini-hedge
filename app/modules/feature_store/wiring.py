"""Feature store module wiring — compute engine, repo, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.feature_store.compute_engine import FeatureComputeEngine
from app.modules.feature_store.repository import FeatureRepository
from app.modules.feature_store.service import FeatureStoreService

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.config import Settings
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings: Settings | None = None,
    **ctx,
) -> None:
    """Wire feature store module."""
    repo = FeatureRepository(sf)
    data_dir = getattr(settings, "alt_data_dir", None) if settings else None
    compute_engine = FeatureComputeEngine(data_dir=data_dir)

    svc = FeatureStoreService(
        repo=repo,
        compute_engine=compute_engine,
        session_factory=sf,
        event_bus=event_bus,
    )
    app.state.feature_store_service = svc
    logger.info("feature_store_module_ready")
