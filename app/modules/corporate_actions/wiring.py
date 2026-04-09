"""Corporate actions module wiring — repo, adapter, service."""

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
    """Wire corporate actions module: repo, adapter, service."""
    from app.adapters.factory import build_corporate_actions_adapter
    from app.modules.corporate_actions.repositories import CorporateActionsRepository
    from app.modules.corporate_actions.services import CorporateActionsService

    repo = CorporateActionsRepository(sf)
    adapter = build_corporate_actions_adapter(settings)

    position_service = app.state.position_service

    service = CorporateActionsService(
        session_factory=sf,
        repo=repo,
        corporate_actions_adapter=adapter,
        event_bus=event_bus,
        position_service=position_service,
    )
    app.state.corporate_actions_service = service
    logger.info("corporate_actions_module_ready")
