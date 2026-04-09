"""Alpha engine module wiring — repo, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.alpha_engine.repository import AlphaRepository
from app.modules.alpha_engine.service import AlphaService

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
    """Wire alpha engine module: repo, service."""
    alpha_repo = AlphaRepository(sf)
    position_service = app.state.position_service
    sm_service = app.state.security_master_service
    alpha_service = AlphaService(
        alpha_repo=alpha_repo,
        position_service=position_service,
        security_master_service=sm_service,
    )
    app.state.alpha_service = alpha_service
