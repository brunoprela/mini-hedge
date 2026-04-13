"""Exposure module wiring — repo, service, event subscriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.market_data.services import MarketDataService
    from app.modules.platform.repositories import FundRepository
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus, EventHandler

from app.modules.exposure.repositories import ExposureRepository
from app.modules.exposure.services import ExposureService
from app.shared.schema_registry import fund_topic, shared_topic

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    fund_repo: FundRepository | None = None,
    **ctx,
) -> None:
    """Wire exposure module: repo, service, event subscriptions."""
    exposure_repo = ExposureRepository(sf)
    position_service = app.state.position_service
    sm_service = app.state.security_master_service
    market_data_service: MarketDataService = app.state.market_data_service
    exposure_service = ExposureService(
        exposure_repo=exposure_repo,
        position_service=position_service,
        security_master_service=sm_service,
        event_bus=event_bus,
        fx_converter=market_data_service.fx_converter,
    )
    app.state.exposure_service = exposure_service

    # Subscribe: recalculate exposure when positions change
    if event_bus is not None and fund_repo is not None:
        active_funds = await fund_repo.get_all_active()
        for fund in active_funds:

            def _make_handler(slug: str) -> EventHandler:
                async def on_position_changed(event: BaseEvent) -> None:
                    pid_str = event.data.get("portfolio_id")
                    if not pid_str:
                        return
                    try:
                        async with sf.fund_scope(slug):
                            await exposure_service.take_snapshot(
                                UUID(pid_str),
                                fund_slug=slug,
                            )
                    except Exception:
                        logger.exception(
                            "exposure_reactive_snapshot_failed",
                            portfolio_id=pid_str,
                        )

                return on_position_changed

            event_bus.subscribe(
                fund_topic(fund.slug, "positions.changed"),
                _make_handler(fund.slug),
            )
        # Also subscribe to prices.normalized (shared topic) to recalculate
        # exposure when market prices change. Throttled: each portfolio
        # recalculates at most once per _EXPOSURE_THROTTLE_SECONDS to avoid
        # a snapshot storm when 50+ instruments tick every second.
        import time

        _EXPOSURE_THROTTLE_SECONDS = 10
        _last_snapshot: dict[str, float] = {}  # portfolio_id → timestamp
        portfolio_repo = getattr(app.state, "portfolio_repo", None)

        async def on_price_normalized(event: BaseEvent) -> None:
            """Recalculate exposure for all portfolios when prices change (throttled)."""
            if portfolio_repo is None:
                return
            now = time.monotonic()
            for fund in active_funds:
                try:
                    portfolios = await portfolio_repo.get_by_fund(fund.id)
                    async with sf.fund_scope(fund.slug):
                        for port in portfolios:
                            last = _last_snapshot.get(port.id, 0.0)
                            if now - last < _EXPOSURE_THROTTLE_SECONDS:
                                continue
                            try:
                                await exposure_service.take_snapshot(
                                    UUID(port.id),
                                    fund_slug=fund.slug,
                                )
                                _last_snapshot[port.id] = now
                            except Exception:
                                logger.exception(
                                    "exposure_price_snapshot_failed",
                                    portfolio_id=port.id,
                                )
                except Exception:
                    logger.exception(
                        "exposure_price_fund_failed",
                        fund_slug=fund.slug,
                    )

        event_bus.subscribe(
            shared_topic("prices.normalized"),
            on_price_normalized,
        )
        logger.info(
            "exposure_subscribed_to_positions_and_prices",
            fund_count=len(active_funds),
        )

    import os

    if os.environ.get("APP_ENV", "local") == "local":
        try:
            from app.modules.exposure.seed import seed_dev_data

            await seed_dev_data(app, sf)
        except Exception:
            logger.debug("exposure_seed_failed", exc_info=True)
