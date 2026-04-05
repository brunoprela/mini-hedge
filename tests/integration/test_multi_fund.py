"""Integration tests for multi-fund schema isolation.

Verifies that each fund's position data lives in its own PostgreSQL schema
and is completely invisible to other funds — the core guarantee of the
schema-per-fund architecture.
"""

from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.positions.event_store import EventStoreRepository
from app.modules.positions.interface import TradeSide
from app.modules.positions.mtm_handler import MarkToMarketHandler
from app.modules.positions.position_projector import PositionProjector
from app.modules.positions.position_repository import CurrentPositionRepository
from app.modules.positions.service import PositionService
from app.modules.positions.trade_handler import TradeHandler
from app.shared.database import TenantSessionFactory
from app.shared.events import BaseEvent, InProcessEventBus
from app.shared.request_context import RequestContext, set_request_context
from app.shared.types import AssetClass
from tests.factories import make_trade


def _build_service(
    session_factory: TenantSessionFactory,
) -> tuple[PositionService, InProcessEventBus]:
    """Wire up a PositionService with in-process event bus."""
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
    return PositionService(position_repo=position_repo, trade_handler=trade_handler), event_bus


@pytest.mark.integration
class TestSchemaIsolation:
    """Verify that positions in one fund are invisible to other funds."""

    @pytest.mark.asyncio
    async def test_fund_alpha_positions_invisible_to_beta(
        self,
        session_factory: TenantSessionFactory,
        alpha_context: RequestContext,
        beta_context: RequestContext,
    ) -> None:
        """Trade in fund-alpha, verify fund-beta sees nothing."""
        service, _ = _build_service(session_factory)

        # Execute a trade as fund-alpha
        set_request_context(alpha_context)
        async with session_factory.fund_scope("alpha"):
            trade = make_trade(
                portfolio_id=UUID("20000000-0000-0000-0000-000000000001"),
                instrument_id="UNH",
                quantity=Decimal("500"),
                price=Decimal("185.50"),
            )
            position = await service.execute_trade(trade, alpha_context)
            assert position.quantity == Decimal("500")

        # Switch to fund-beta context — should see zero positions
        set_request_context(beta_context)
        async with session_factory.fund_scope("beta"):
            beta_positions = await service.get_by_portfolio(
                UUID("20000000-0000-0000-0000-000000000010"),
            )
            assert len(beta_positions) == 0

    @pytest.mark.asyncio
    async def test_fund_beta_positions_invisible_to_gamma(
        self,
        session_factory: TenantSessionFactory,
        beta_context: RequestContext,
        gamma_context: RequestContext,
    ) -> None:
        """Trade in fund-beta, verify fund-gamma sees nothing."""
        service, _ = _build_service(session_factory)

        # Execute a trade as fund-beta
        set_request_context(beta_context)
        async with session_factory.fund_scope("beta"):
            trade = make_trade(
                portfolio_id=UUID("20000000-0000-0000-0000-000000000010"),
                instrument_id="NVDA",
                quantity=Decimal("200"),
                price=Decimal("920.00"),
            )
            position = await service.execute_trade(trade, beta_context)
            assert position.quantity == Decimal("200")

        # Switch to fund-gamma — should see zero positions
        set_request_context(gamma_context)
        async with session_factory.fund_scope("gamma"):
            gamma_positions = await service.get_by_portfolio(
                UUID("20000000-0000-0000-0000-000000000020"),
            )
            assert len(gamma_positions) == 0

    @pytest.mark.asyncio
    async def test_concurrent_trades_across_funds(
        self,
        session_factory: TenantSessionFactory,
        alpha_context: RequestContext,
        beta_context: RequestContext,
        gamma_context: RequestContext,
    ) -> None:
        """All three funds trade the same instrument — each sees only its own position."""
        service, _ = _build_service(session_factory)

        alpha_pid = UUID("20000000-0000-0000-0000-000000000001")
        beta_pid = UUID("20000000-0000-0000-0000-000000000010")
        gamma_pid = UUID("20000000-0000-0000-0000-000000000020")
        trades = [
            (alpha_context, "alpha", alpha_pid, Decimal("100"), Decimal("195.00")),
            (beta_context, "beta", beta_pid, Decimal("250"), Decimal("196.50")),
            (gamma_context, "gamma", gamma_pid, Decimal("75"), Decimal("194.25")),
        ]

        for ctx, slug, portfolio_id, qty, price in trades:
            set_request_context(ctx)
            async with session_factory.fund_scope(slug):
                trade = make_trade(
                    portfolio_id=portfolio_id,
                    instrument_id="JPM",
                    quantity=qty,
                    price=price,
                )
                await service.execute_trade(trade, ctx)

        # Verify each fund sees only its own position
        set_request_context(alpha_context)
        async with session_factory.fund_scope("alpha"):
            alpha_pos = await service.get_position(alpha_pid, "JPM")
            assert alpha_pos is not None
            assert alpha_pos.quantity == Decimal("100")
            assert alpha_pos.avg_cost == Decimal("195.00")

        set_request_context(beta_context)
        async with session_factory.fund_scope("beta"):
            beta_pos = await service.get_position(beta_pid, "JPM")
            assert beta_pos is not None
            assert beta_pos.quantity == Decimal("250")
            assert beta_pos.avg_cost == Decimal("196.50")

        set_request_context(gamma_context)
        async with session_factory.fund_scope("gamma"):
            gamma_pos = await service.get_position(gamma_pid, "JPM")
            assert gamma_pos is not None
            assert gamma_pos.quantity == Decimal("75")
            assert gamma_pos.avg_cost == Decimal("194.25")


@pytest.mark.integration
class TestMultiFundPnL:
    """Cross-fund P&L isolation — realized P&L stays within its fund."""

    @pytest.mark.asyncio
    async def test_pnl_isolated_per_fund(
        self,
        session_factory: TenantSessionFactory,
        alpha_context: RequestContext,
        beta_context: RequestContext,
    ) -> None:
        """Fund-alpha realizes P&L, fund-beta's position is unaffected."""
        service, _ = _build_service(session_factory)

        # Alpha: buy then sell MA at profit
        set_request_context(alpha_context)
        alpha_portfolio = UUID("20000000-0000-0000-0000-000000000001")
        async with session_factory.fund_scope("alpha"):
            await service.execute_trade(
                make_trade(
                    portfolio_id=alpha_portfolio,
                    instrument_id="MA",
                    side=TradeSide.BUY,
                    quantity=Decimal("100"),
                    price=Decimal("410.00"),
                ),
                alpha_context,
            )
            sell_pos = await service.execute_trade(
                make_trade(
                    portfolio_id=alpha_portfolio,
                    instrument_id="MA",
                    side=TradeSide.SELL,
                    quantity=Decimal("100"),
                    price=Decimal("425.00"),
                ),
                alpha_context,
            )
            assert sell_pos.quantity == Decimal("0")

        # Beta: buy MA — should have clean position with no realized P&L
        set_request_context(beta_context)
        beta_portfolio = UUID("20000000-0000-0000-0000-000000000010")
        async with session_factory.fund_scope("beta"):
            beta_pos = await service.execute_trade(
                make_trade(
                    portfolio_id=beta_portfolio,
                    instrument_id="MA",
                    side=TradeSide.BUY,
                    quantity=Decimal("50"),
                    price=Decimal("420.00"),
                ),
                beta_context,
            )
            assert beta_pos.quantity == Decimal("50")
            assert beta_pos.avg_cost == Decimal("420.00")
            assert beta_pos.unrealized_pnl == Decimal("0")


@pytest.mark.integration
class TestMarkToMarketCrossFund:
    """MTM handler updates positions across all fund schemas."""

    @pytest.mark.asyncio
    async def test_mtm_updates_all_funds(
        self,
        session_factory: TenantSessionFactory,
        alpha_context: RequestContext,
        beta_context: RequestContext,
    ) -> None:
        """Price update for GS flows through to both funds' positions."""
        service, event_bus = _build_service(session_factory)

        # Alpha buys GS
        set_request_context(alpha_context)
        alpha_portfolio = UUID("20000000-0000-0000-0000-000000000001")
        async with session_factory.fund_scope("alpha"):
            await service.execute_trade(
                make_trade(
                    portfolio_id=alpha_portfolio,
                    instrument_id="GS",
                    quantity=Decimal("30"),
                    price=Decimal("450.00"),
                ),
                alpha_context,
            )

        # Beta buys GS
        set_request_context(beta_context)
        beta_portfolio = UUID("20000000-0000-0000-0000-000000000010")
        async with session_factory.fund_scope("beta"):
            await service.execute_trade(
                make_trade(
                    portfolio_id=beta_portfolio,
                    instrument_id="GS",
                    quantity=Decimal("80"),
                    price=Decimal("455.00"),
                ),
                beta_context,
            )

        # MTM handler with known fund slugs and asset class resolver
        async def get_fund_slugs() -> list[str]:
            return ["alpha", "beta"]

        async def get_asset_class(instrument_id: str) -> AssetClass | None:
            return AssetClass.EQUITY

        mtm_handler = MarkToMarketHandler(
            session_factory=session_factory,
            event_bus=event_bus,
            get_fund_slugs=get_fund_slugs,
            get_asset_class=get_asset_class,
        )

        price_event = BaseEvent(
            event_type="price.updated",
            data={
                "instrument_id": "GS",
                "bid": "459.50",
                "ask": "460.50",
                "mid": "460.00",
                "timestamp": "2026-04-02T12:00:00Z",
                "source": "test",
            },
        )
        await mtm_handler.handle_price_update(price_event)

        # Verify alpha's GS position was marked to market
        set_request_context(alpha_context)
        async with session_factory.fund_scope("alpha"):
            alpha_repo = CurrentPositionRepository(session_factory)
            alpha_pos = await alpha_repo.get_position(alpha_portfolio, "GS")
            assert alpha_pos is not None
            assert alpha_pos.market_price == Decimal("460.00")
            assert alpha_pos.market_value == Decimal("13800.00")
            assert alpha_pos.unrealized_pnl == Decimal("300.00")

        # Verify beta's GS position was also marked to market
        set_request_context(beta_context)
        async with session_factory.fund_scope("beta"):
            beta_repo = CurrentPositionRepository(session_factory)
            beta_pos = await beta_repo.get_position(beta_portfolio, "GS")
            assert beta_pos is not None
            assert beta_pos.market_price == Decimal("460.00")
            assert beta_pos.market_value == Decimal("36800.00")
            assert beta_pos.unrealized_pnl == Decimal("400.00")


@pytest.mark.integration
class TestEventStoreIsolation:
    """Event store entries are isolated per-fund schema."""

    @pytest.mark.asyncio
    async def test_event_store_per_fund(
        self,
        session_factory: TenantSessionFactory,
        alpha_context: RequestContext,
        beta_context: RequestContext,
    ) -> None:
        """Events from fund-alpha's trades don't appear in fund-beta's event store."""
        service, _ = _build_service(session_factory)
        event_store = EventStoreRepository(session_factory)

        # Alpha trades TSLA
        set_request_context(alpha_context)
        alpha_portfolio = UUID("20000000-0000-0000-0000-000000000001")
        async with session_factory.fund_scope("alpha"):
            await service.execute_trade(
                make_trade(
                    portfolio_id=alpha_portfolio,
                    instrument_id="TSLA",
                    quantity=Decimal("20"),
                    price=Decimal("250.00"),
                ),
                alpha_context,
            )

            # Alpha's event store should have the trade event
            aggregate_id = f"{alpha_portfolio}:TSLA"
            alpha_events = await event_store.get_by_aggregate(aggregate_id)
            assert len(alpha_events) >= 1
            assert alpha_events[0].event_type in ("trade.buy", "trade.sell")

        # Beta's event store — same aggregate_id pattern but different schema
        set_request_context(beta_context)
        async with session_factory.fund_scope("beta"):
            beta_portfolio = UUID("20000000-0000-0000-0000-000000000010")
            beta_aggregate = f"{beta_portfolio}:TSLA"
            beta_events = await event_store.get_by_aggregate(beta_aggregate)
            assert len(beta_events) == 0
