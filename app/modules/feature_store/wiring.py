"""Feature store module wiring — compute engine, repos, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.feature_store.core.compute_engine import FeatureComputeEngine
from app.modules.feature_store.repositories import (
    FeatureDefinitionRepository,
    FeatureSetRepository,
    FeatureValueRepository,
)
from app.modules.feature_store.services import FeatureStoreService

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
    definition_repo = FeatureDefinitionRepository(sf)
    value_repo = FeatureValueRepository(sf)
    set_repo = FeatureSetRepository(sf)

    data_dir = getattr(settings, "alt_data_dir", None) if settings else None
    compute_engine = FeatureComputeEngine(data_dir=data_dir)

    svc = FeatureStoreService(
        definition_repo=definition_repo,
        value_repo=value_repo,
        set_repo=set_repo,
        compute_engine=compute_engine,
        session_factory=sf,
        event_bus=event_bus,
    )
    app.state.feature_store_service = svc
    logger.info("feature_store_module_ready")
