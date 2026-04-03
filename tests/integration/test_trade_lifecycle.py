"""E2E trade lifecycle — buy, MTM, sell, verify full position state."""

from decimal import Decimal

import pytest

from app.modules.positions.handlers import MarkToMarketHandler, TradeHandler
from app.modules.positions.interface import TradeSide
from app.modules.positions.repository import CurrentPositionRepository, EventStoreRepository
from app.modules.positions.service import PositionService
from app.shared.database import TenantSessionFactory
from app.shared.events import BaseEvent, InProcessEventBus
from app.shared.request_context import RequestContext
from app.shared.types import AssetClass
from tests.factories import DEFAULT_PORTFOLIO_ID, make_trade


@pytest.mark.integration
class TestTradeLifecycle:
    """Full buy -> MTM -> partial sell -> verify PnL lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(
        self,
        session_factory: TenantSessionFactory,
        request_context: RequestContext,
    ) -> None:
        event_bus = InProcessEventBus()
        event_store = EventStoreRepository(session_factory)
        position_repo = CurrentPositionRepository(session_factory)
        trade_handler = TradeHandler(session_factory, event_store, position_repo, event_bus)
        service = PositionService(position_repo, trade_handler)

        # Step 1: Buy 100 NFLX @ $200 (unique ticker for this test)
        buy = make_trade(
            instrument_id="NFLX",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("200.00"),
        )
        pos = await service.execute_trade(buy, request_context)
        assert pos.quantity == Decimal("100")
        assert pos.cost_basis == Decimal("20000")
        assert pos.avg_cost == Decimal("200")

        # Step 2: Mark-to-market at $220
        async def get_fund_slugs() -> list[str]:
            return ["alpha"]

        async def get_asset_class(instrument_id: str) -> AssetClass | None:
            return AssetClass.EQUITY

        mtm = MarkToMarketHandler(session_factory, event_bus, get_fund_slugs, get_asset_class)
        price_event = BaseEvent(
            event_type="price.updated",
            data={"instrument_id": "NFLX", "mid": "220.00"},
        )
        await mtm.handle_price_update(price_event)

        # Verify MTM updated market_value and unrealized_pnl
        pos = await service.get_position(DEFAULT_PORTFOLIO_ID, "NFLX")
        assert pos is not None
        assert pos.market_price == Decimal("220")
        assert pos.market_value == Decimal("22000")  # 100 * 220
        assert pos.unrealized_pnl == Decimal("2000")  # 22000 - 20000

        # Step 3: Partial sell — 60 shares @ $225
        sell = make_trade(
            instrument_id="NFLX",
            side=TradeSide.SELL,
            quantity=Decimal("60"),
            price=Decimal("225.00"),
        )
        pos = await service.execute_trade(sell, request_context)
        assert pos.quantity == Decimal("40")
        # cost_basis after selling 60 from lot of 100 @ $200: 40 * 200 = 8000
        assert pos.cost_basis == Decimal("8000")

        # Realized P&L from the sell: 60 * (225 - 200) = 1500
        record = await position_repo.get_position(DEFAULT_PORTFOLIO_ID, "NFLX")
        assert record is not None
        assert record.realized_pnl == Decimal("1500")

        # Step 4: Verify event store has 2 events (buy + sell)
        events = await event_store.get_by_aggregate(f"{DEFAULT_PORTFOLIO_ID}:NFLX")
        assert len(events) == 2
        assert events[0]["event_type"] == "trade.buy"
        assert events[1]["event_type"] == "trade.sell"

    @pytest.mark.asyncio
    async def test_short_sell_lifecycle(
        self,
        session_factory: TenantSessionFactory,
        request_context: RequestContext,
    ) -> None:
        """Short sell -> cover -> verify PnL."""
        event_bus = InProcessEventBus()
        event_store = EventStoreRepository(session_factory)
        position_repo = CurrentPositionRepository(session_factory)
        trade_handler = TradeHandler(session_factory, event_store, position_repo, event_bus)
        service = PositionService(position_repo, trade_handler)

        # Short 50 CRM @ $500 (unique ticker for this test)
        short = make_trade(
            instrument_id="CRM",
            side=TradeSide.SELL,
            quantity=Decimal("50"),
            price=Decimal("500.00"),
        )
        pos = await service.execute_trade(short, request_context)
        assert pos.quantity == Decimal("-50")
        assert pos.cost_basis == Decimal("25000")  # abs(-50) * 500

        # Cover (buy back) at $480 — profit
        cover = make_trade(
            instrument_id="CRM",
            side=TradeSide.BUY,
            quantity=Decimal("50"),
            price=Decimal("480.00"),
        )
        pos = await service.execute_trade(cover, request_context)
        assert pos.quantity == Decimal("0")
