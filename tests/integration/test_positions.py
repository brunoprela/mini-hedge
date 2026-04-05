"""Integration tests for position keeping module."""

from decimal import Decimal

import pytest
import pytest_asyncio

from app.modules.positions.event_store import EventStoreRepository
from app.modules.positions.interface import TradeSide
from app.modules.positions.position_projector import PositionProjector
from app.modules.positions.position_repository import CurrentPositionRepository
from app.modules.positions.service import PositionService
from app.modules.positions.trade_handler import TradeHandler
from app.shared.database import TenantSessionFactory
from app.shared.events import InProcessEventBus
from app.shared.request_context import RequestContext
from tests.factories import DEFAULT_PORTFOLIO_ID, make_trade


@pytest_asyncio.fixture
async def position_service(session_factory: TenantSessionFactory) -> PositionService:
    event_bus = InProcessEventBus()
    event_store = EventStoreRepository(session_factory)
    position_repo = CurrentPositionRepository(session_factory)
    projector = PositionProjector(position_repo)
    trade_handler = TradeHandler(
        session_factory=session_factory,
        event_store=event_store,
        projector=projector,
        event_bus=event_bus,
    )
    return PositionService(position_repo=position_repo, trade_handler=trade_handler)


@pytest.mark.integration
class TestPositionKeeping:
    @pytest.mark.asyncio
    async def test_buy_creates_position(
        self,
        session_factory: TenantSessionFactory,
        request_context: RequestContext,
        position_service: PositionService,
    ) -> None:
        async with session_factory.fund_scope("alpha"):
            trade = make_trade(instrument_id="V", quantity=Decimal("100"), price=Decimal("150.00"))
            position = await position_service.execute_trade(trade, request_context)

        assert position.quantity == Decimal("100")
        assert position.avg_cost == Decimal("150.00")
        assert position.cost_basis == Decimal("15000.00")

    @pytest.mark.asyncio
    async def test_buy_then_sell_realizes_pnl(
        self,
        session_factory: TenantSessionFactory,
        request_context: RequestContext,
        position_service: PositionService,
    ) -> None:
        position_repo = CurrentPositionRepository(session_factory)

        async with session_factory.fund_scope("alpha"):
            buy = make_trade(
                instrument_id="JNJ",
                side=TradeSide.BUY,
                quantity=Decimal("50"),
                price=Decimal("400.00"),
            )
            await position_service.execute_trade(buy, request_context)

            sell = make_trade(
                instrument_id="JNJ",
                side=TradeSide.SELL,
                quantity=Decimal("50"),
                price=Decimal("420.00"),
            )
            position = await position_service.execute_trade(sell, request_context)

            assert position.quantity == Decimal("0")
            record = await position_repo.get_position(buy.portfolio_id, "JNJ")
            assert record is not None
            assert record.realized_pnl == Decimal("1000")

    @pytest.mark.asyncio
    async def test_portfolio_positions(
        self,
        session_factory: TenantSessionFactory,
        request_context: RequestContext,
        position_service: PositionService,
    ) -> None:
        async with session_factory.fund_scope("alpha"):
            await position_service.execute_trade(
                make_trade(instrument_id="XOM", quantity=Decimal("10"), price=Decimal("175.00")),
                request_context,
            )
            await position_service.execute_trade(
                make_trade(instrument_id="BAC", quantity=Decimal("5"), price=Decimal("880.00")),
                request_context,
            )

            positions = await position_service.get_by_portfolio(DEFAULT_PORTFOLIO_ID)
            tickers = {p.instrument_id for p in positions}
            assert "XOM" in tickers
            assert "BAC" in tickers
