"""FX hedging module wiring — repos, service, interest rate event handler."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.fx_hedging.repositories import (
    FXForwardRepository,
    FXInterestRateRepository,
)
from app.modules.fx_hedging.services import FXHedgingService
from app.shared.schema_registry import shared_topic

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus, EventHandler

logger = structlog.get_logger()


def _make_interest_rate_handler(fx_hedging_service: FXHedgingService) -> EventHandler:
    """Create a handler that updates FX hedging interest rates from Kafka.

    The mock exchange publishes interest_rate.updated events with pillar
    rates per currency on the shared.interest-rates topic.
    """

    async def on_interest_rate_event(event: BaseEvent) -> None:
        try:
            data = event.data
            currency = data.get("currency")
            rate_1m = data.get("rate_1m")
            if currency is None or rate_1m is None:
                return
            await fx_hedging_service.set_interest_rate(
                currency=currency,
                rate=Decimal(rate_1m),
                tenor_days=30,
                source="mock-exchange",
            )
        except Exception:
            logger.exception(
                "interest_rate_handler_failed",
                event_id=event.event_id,
            )

    return on_interest_rate_event


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> None:
    """Wire FX hedging module: repos, service."""
    market_data_service = app.state.market_data_service
    fx_converter = market_data_service.fx_converter

    forward_repo = FXForwardRepository(sf)
    rate_repo = FXInterestRateRepository(sf)

    fx_hedging_service = FXHedgingService(
        forward_repo=forward_repo,
        rate_repo=rate_repo,
        event_bus=event_bus,
        fx_converter=fx_converter,
    )
    app.state.fx_hedging_service = fx_hedging_service

    # Subscribe to interest rate updates from mock exchange
    if event_bus is not None:
        event_bus.subscribe(
            shared_topic("interest-rates"),
            _make_interest_rate_handler(fx_hedging_service),
        )

    # Seed FX hedging data in local environment
    if os.environ.get("APP_ENV", "local") == "local":
        from app.modules.fx_hedging.seed import seed_dev_data

        await seed_dev_data(app, sf)

    logger.info("fx_hedging_module_ready")
