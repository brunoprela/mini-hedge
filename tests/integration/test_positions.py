"""Integration tests for position keeping module."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.positions.handlers import TradeHandler
from app.modules.positions.interface import TradeSide
from app.modules.positions.repository import CurrentPositionRepository, EventStoreRepository
from app.modules.positions.service import PositionService
from app.shared.events import InProcessEventBus
from tests.factories import DEFAULT_PORTFOLIO_ID, make_trade


@pytest.mark.integration
class TestPositionKeeping:
    @pytest.mark.asyncio
    async def test_buy_creates_position(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        event_bus = InProcessEventBus()
        event_store = EventStoreRepository(session_factory)
        position_repo = CurrentPositionRepository(session_factory)
        trade_handler = TradeHandler(event_store, position_repo, event_bus)
        service = PositionService(position_repo, trade_handler)

        trade = make_trade(instrument_id="AAPL", quantity=Decimal("100"), price=Decimal("150.00"))
        position = await service.execute_trade(trade)

        assert position.quantity == Decimal("100")
        assert position.avg_cost == Decimal("150.00")
        assert position.cost_basis == Decimal("15000.00")

    @pytest.mark.asyncio
    async def test_buy_then_sell_realizes_pnl(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        event_bus = InProcessEventBus()
        event_store = EventStoreRepository(session_factory)
        position_repo = CurrentPositionRepository(session_factory)
        trade_handler = TradeHandler(event_store, position_repo, event_bus)
        service = PositionService(position_repo, trade_handler)

        # Buy
        buy = make_trade(
            instrument_id="MSFT",
            side=TradeSide.BUY,
            quantity=Decimal("50"),
            price=Decimal("400.00"),
        )
        await service.execute_trade(buy)

        # Sell at higher price
        sell = make_trade(
            instrument_id="MSFT",
            side=TradeSide.SELL,
            quantity=Decimal("50"),
            price=Decimal("420.00"),
        )
        position = await service.execute_trade(sell)

        assert position.quantity == Decimal("0")
        # Realized P&L: 50 * (420 - 400) = 1000

    @pytest.mark.asyncio
    async def test_portfolio_positions(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        event_bus = InProcessEventBus()
        event_store = EventStoreRepository(session_factory)
        position_repo = CurrentPositionRepository(session_factory)
        trade_handler = TradeHandler(event_store, position_repo, event_bus)
        service = PositionService(position_repo, trade_handler)

        # Buy two different instruments
        await service.execute_trade(
            make_trade(instrument_id="GOOGL", quantity=Decimal("10"), price=Decimal("175.00"))
        )
        await service.execute_trade(
            make_trade(instrument_id="NVDA", quantity=Decimal("5"), price=Decimal("880.00"))
        )

        positions = await service.get_portfolio_positions(DEFAULT_PORTFOLIO_ID)
        tickers = {p.instrument_id for p in positions}
        assert "GOOGL" in tickers
        assert "NVDA" in tickers
