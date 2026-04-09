"""Regulatory reporting module wiring."""

from __future__ import annotations

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
    """Wire regulatory reporting module."""
    from app.modules.regulatory.repository import RegulatoryRepository
    from app.modules.regulatory.service import RegulatoryService

    repo = RegulatoryRepository(sf)

    svc = RegulatoryService(
        repo=repo,
        position_service=getattr(app.state, "position_service", None),
        capital_service=getattr(app.state, "capital_service", None),
        risk_service=getattr(app.state, "risk_service", None),
        exposure_service=getattr(app.state, "exposure_service", None),
        security_master_service=getattr(app.state, "sm_service", None),
    )
    app.state.regulatory_service = svc
    logger.info("regulatory_module_ready")
