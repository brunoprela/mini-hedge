"""Market data module wiring — repo, service, price + FX event handlers."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus, EventHandler

from app.modules.market_data.interfaces import FXRateSnapshot, PriceSnapshot
from app.modules.market_data.repositories import FXRateRepository, PriceRepository
from app.modules.market_data.services import MarketDataService
from app.shared.schema_registry import shared_topic

logger = structlog.get_logger()


def _make_price_handler(market_data_service: MarketDataService) -> EventHandler:
    """Create a price event handler for equity/instrument prices."""

    _required_fields = ("instrument_id", "bid", "ask", "mid", "source")

    async def on_price_event(event: BaseEvent) -> None:
        try:
            data = event.data
            instrument_id: str = data.get("instrument_id", "")

            if not all(k in data for k in _required_fields):
                logger.warning(
                    "price_event_missing_fields",
                    event_id=event.event_id,
                    keys=list(data.keys()),
                )
                return
            raw_volume = data.get("volume")
            snapshot = PriceSnapshot(
                instrument_id=instrument_id,
                bid=Decimal(data["bid"]),
                ask=Decimal(data["ask"]),
                mid=Decimal(data["mid"]),
                volume=Decimal(raw_volume) if raw_volume is not None else None,
                timestamp=event.timestamp,
                source=data["source"],
            )
            market_data_service.update_latest(snapshot)
            await market_data_service.store_price(snapshot)
        except Exception:
            logger.exception("price_event_handler_failed", event_id=event.event_id)

    return on_price_event


def _make_fx_rate_handler(market_data_service: MarketDataService) -> EventHandler:
    """Create a handler for FX rate events on the dedicated fx-rates topic."""

    async def on_fx_rate_event(event: BaseEvent) -> None:
        try:
            data = event.data
            instrument_id: str = data.get("instrument_id", "")

            pair = instrument_id.removeprefix("FX:")
            parts = pair.split("/")
            if len(parts) != 2:
                logger.warning("fx_event_bad_pair", pair=pair)
                return
            rate_str = data.get("mid") or data.get("rate")
            if rate_str is None:
                logger.warning("fx_event_missing_rate", pair=pair)
                return
            fx_snapshot = FXRateSnapshot(
                base_currency=parts[0],
                quote_currency=parts[1],
                rate=Decimal(rate_str),
                timestamp=event.timestamp,
                source=data.get("source", "mock-exchange"),
            )
            market_data_service.update_fx_rate(fx_snapshot)
            await market_data_service.store_fx_rate(fx_snapshot)
        except Exception:
            logger.exception("fx_rate_event_handler_failed", event_id=event.event_id)

    return on_fx_rate_event


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> MarketDataService:
    """Wire market data module: repo, service, price + FX event handler."""
    price_repo = PriceRepository(sf)
    fx_repo = FXRateRepository(sf)
    market_data_service = MarketDataService(repository=price_repo, fx_repository=fx_repo)
    app.state.market_data_service = market_data_service

    if event_bus is not None:
        price_handler = _make_price_handler(market_data_service)
        event_bus.subscribe(shared_topic("prices.normalized"), price_handler)
        fx_rate_handler = _make_fx_rate_handler(market_data_service)
        event_bus.subscribe(shared_topic("fx-rates.normalized"), fx_rate_handler)

    return market_data_service
