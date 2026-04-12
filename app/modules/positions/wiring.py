"""Positions module wiring — repos, projector, handlers, service, subscriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository
    from app.modules.platform.services import AdminService
    from app.modules.security_master.services import SecurityMasterService
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus
    from app.shared.types import AssetClass

from app.modules.positions.core.event_store import EventStoreRepository
from app.modules.positions.core.mtm_handler import MarkToMarketHandler
from app.modules.positions.core.position_projector import PositionProjector
from app.modules.positions.core.trade_handler import TradeHandler
from app.modules.positions.repositories import CurrentPositionRepository, LotRepository
from app.modules.positions.repositories.daily_pnl import DailyPnLRepository
from app.modules.positions.services import PositionService
from app.shared.schema_registry import fund_topic, shared_topic

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    fund_repo: FundRepository | None = None,
    security_master_service: SecurityMasterService | None = None,
    **ctx,
) -> None:
    """Wire positions module: repos, projector, handlers, service, MTM + trade subscriptions."""
    event_store_repo = EventStoreRepository(sf)
    position_repo = CurrentPositionRepository(sf)
    lot_repo = LotRepository(sf)
    projector = PositionProjector(position_repo)
    trade_handler = TradeHandler(
        session_factory=sf,
        event_store=event_store_repo,
        projector=projector,
        event_bus=event_bus,
    )
    app.state.trade_handler = trade_handler
    daily_pnl_repo = DailyPnLRepository(sf)
    app.state.position_service = PositionService(
        position_repo=position_repo,
        lot_repo=lot_repo,
        trade_handler=trade_handler,
        event_store=event_store_repo,
        daily_pnl_repo=daily_pnl_repo,
    )

    # Subscribe trade handler to trades.executed per fund.
    # When an order is filled, OrderService publishes trades.executed;
    # TradeHandler picks it up here, creates the position, and publishes
    # positions.changed — triggering the exposure/risk/compliance cascade.
    active_funds = await fund_repo.get_all_active()
    for fund in active_funds:
        event_bus.subscribe(
            fund_topic(fund.slug, "trades.executed"),
            trade_handler.handle_trade_event,
        )
    logger.info("positions_subscribed_to_trades", fund_count=len(active_funds))

    # Register hook so dynamically-created funds also get the subscription
    async def _on_fund_created(slug: str) -> None:
        event_bus.subscribe(
            fund_topic(slug, "trades.executed"),
            trade_handler.handle_trade_event,
        )

    admin_svc: AdminService | None = getattr(app.state, "admin_service", None)
    if admin_svc is not None:
        admin_svc._fund_service.register_on_fund_created(_on_fund_created)

    async def get_fund_slugs() -> list[str]:
        funds = await fund_repo.get_all_active()
        return [f.slug for f in funds]

    async def get_asset_class(instrument_id: str) -> AssetClass | None:
        try:
            instrument = await security_master_service.get_by_ticker(instrument_id)
        except Exception:
            return None
        return instrument.asset_class

    mtm_handler = MarkToMarketHandler(
        session_factory=sf,
        event_bus=event_bus,
        get_fund_slugs=get_fund_slugs,
        get_asset_class=get_asset_class,
    )
    event_bus.subscribe(shared_topic("prices.normalized"), mtm_handler.handle_price_update)
