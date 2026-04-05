"""Event handler for mark-to-market — revalues positions when prices update."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.positions.interface import (
    PnLMarkToMarket,
    PnLMarkToMarketData,
    PositionEventType,
)
from app.modules.positions.position_repository import CurrentPositionRepository
from app.modules.positions.strategy import PositionStrategy, get_position_strategy
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus
    from app.shared.types import AssetClass

logger = structlog.get_logger()

# Suppress noise: skip publishing if change < 0.01% of position market value
_MTM_NOISE_THRESHOLD = Decimal("0.0001")


class MarkToMarketHandler:
    """Revalues positions when prices update.

    Iterates over all active fund schemas to update every fund's positions.
    Publishes pnl.mark_to_market events when the change exceeds the noise threshold.
    """

    def __init__(
        self,
        *,
        session_factory: TenantSessionFactory,
        event_bus: EventBus,
        get_fund_slugs: Callable[[], Awaitable[list[str]]],
        get_asset_class: Callable[[str], Awaitable[AssetClass | None]],
    ) -> None:
        self._sf = session_factory
        self._event_bus = event_bus
        self._get_fund_slugs = get_fund_slugs
        self._get_asset_class = get_asset_class

    async def handle_price_update(self, event: BaseEvent) -> None:
        try:
            instrument_id = event.data["instrument_id"]
            new_price = Decimal(event.data["mid"])

            asset_class = await self._get_asset_class(instrument_id)
            if asset_class is None:
                logger.warning("mtm_unknown_instrument", instrument_id=instrument_id)
                return
            try:
                strategy = get_position_strategy(asset_class)
            except KeyError:
                logger.warning(
                    "mtm_no_strategy",
                    instrument_id=instrument_id,
                    asset_class=asset_class,
                )
                return

            for slug in await self._get_fund_slugs():
                await self._update_fund_positions(
                    slug,
                    instrument_id,
                    new_price,
                    strategy,
                )
        except Exception:
            logger.exception(
                "mtm_handler_failed",
                event_id=event.event_id,
            )

    async def _update_fund_positions(
        self,
        fund_slug: str,
        instrument_id: str,
        new_price: Decimal,
        strategy: PositionStrategy,
    ) -> None:
        async with self._sf.fund_scope(fund_slug):
            await self._update_positions_for_instrument(
                fund_slug,
                instrument_id,
                new_price,
                strategy,
            )

    async def _update_positions_for_instrument(
        self,
        fund_slug: str,
        instrument_id: str,
        new_price: Decimal,
        strategy: PositionStrategy,
    ) -> None:
        repo = CurrentPositionRepository(self._sf)
        positions = await repo.get_by_instrument(instrument_id)
        for pos in positions:
            old_unrealized = pos.unrealized_pnl
            new_market_value = strategy.market_value(pos.quantity, new_price)
            new_unrealized = strategy.unrealized_pnl(pos.quantity, pos.cost_basis, new_price)
            await repo.update_market_value(
                portfolio_id=UUID(pos.portfolio_id),
                instrument_id=instrument_id,
                market_price=new_price,
                market_value=new_market_value,
                unrealized_pnl=new_unrealized,
            )

            # Publish MTM event if change exceeds noise threshold
            pnl_change = new_unrealized - old_unrealized
            threshold = abs(new_market_value) * _MTM_NOISE_THRESHOLD
            if abs(pnl_change) > threshold:
                mtm_event = PnLMarkToMarket(
                    event_type=PositionEventType.PNL_MARK_TO_MARKET,
                    data=PnLMarkToMarketData(
                        portfolio_id=UUID(pos.portfolio_id),
                        instrument_id=instrument_id,
                        market_price=new_price,
                        market_value=new_market_value,
                        unrealized_pnl=new_unrealized,
                        pnl_change=pnl_change,
                        currency=pos.currency,
                    ),
                )
                topic = fund_topic(fund_slug, "pnl.updated")
                data = asdict(mtm_event.data)
                serialized_data = {k: str(v) for k, v in data.items()}
                await self._event_bus.publish(
                    topic,
                    BaseEvent(
                        event_type=mtm_event.event_type,
                        data=serialized_data,
                        actor_id="system",
                        actor_type="system",
                        fund_slug=fund_slug,
                    ),
                )
