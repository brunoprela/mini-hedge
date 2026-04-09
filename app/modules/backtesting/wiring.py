"""Backtesting module wiring — engine, repo, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.backtesting.engine import BacktestEngine
from app.modules.backtesting.repository import BacktestRepository
from app.modules.backtesting.service import BacktestingService

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
    """Wire backtesting engine module."""
    repo = BacktestRepository(sf)
    engine = BacktestEngine()

    svc = BacktestingService(
        repo=repo,
        engine=engine,
        session_factory=sf,
        event_bus=event_bus,
    )
    app.state.backtesting_service = svc
    logger.info("backtesting_module_ready")
