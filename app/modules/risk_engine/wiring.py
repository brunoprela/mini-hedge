"""Risk engine module wiring — repos, service, event subscriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.risk_engine.repository import RiskRepository
from app.modules.risk_engine.service import RiskService
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.fund_repository import FundRepository
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus, EventHandler

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> None:
    """Wire risk engine module: repo, service, event subscriptions."""
    risk_repo = RiskRepository(sf)
    position_service = app.state.position_service
    market_data_service = app.state.market_data_service
    sm_service = app.state.security_master_service
    risk_service = RiskService(
        risk_repo=risk_repo,
        position_service=position_service,
        market_data_service=market_data_service,
        security_master_service=sm_service,
        event_bus=event_bus,
        fx_converter=market_data_service.fx_converter,
    )
    app.state.risk_service = risk_service

    # Subscribe: recalculate risk when positions change
    if event_bus is not None:
        fund_repo: FundRepository = app.state.fund_repo
        active_funds = await fund_repo.get_all_active()
        for fund in active_funds:

            def _make_handler(slug: str) -> EventHandler:
                async def on_position_changed(event: BaseEvent) -> None:
                    pid_str = event.data.get("portfolio_id")
                    if not pid_str:
                        return
                    try:
                        await risk_service.take_snapshot(
                            UUID(pid_str),
                            fund_slug=slug,
                        )
                    except Exception:
                        logger.exception(
                            "risk_reactive_snapshot_failed",
                            portfolio_id=pid_str,
                        )

                return on_position_changed

            event_bus.subscribe(
                fund_topic(fund.slug, "positions.changed"),
                _make_handler(fund.slug),
            )
        logger.info(
            "risk_subscribed_to_positions",
            fund_count=len(active_funds),
        )
