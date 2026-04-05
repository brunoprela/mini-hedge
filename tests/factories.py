"""Test fixture factories — sensible defaults, override only what matters."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.market_data.interface import PriceSnapshot
from app.modules.orders.interface import CreateOrderRequest, OrderSide, OrderType
from app.modules.platform.seed import (
    PORTFOLIO_ALPHA_EQUITY_LS_ID,
    PORTFOLIO_BETA_STAT_ARB_ID,
    PORTFOLIO_GAMMA_EVENT_DRIVEN_ID,
)
from app.modules.positions.interface import (
    PositionEventType,
    TradeEvent,
    TradeEventData,
    TradeRequest,
    TradeSide,
)
from app.modules.security_master.interface import Instrument
from app.shared.events import BaseEvent
from app.shared.types import AssetClass

# Well-known portfolio IDs matching seed data
DEFAULT_PORTFOLIO_ID = UUID(PORTFOLIO_ALPHA_EQUITY_LS_ID)
BETA_PORTFOLIO_ID = UUID(PORTFOLIO_BETA_STAT_ARB_ID)
GAMMA_PORTFOLIO_ID = UUID(PORTFOLIO_GAMMA_EVENT_DRIVEN_ID)


def make_instrument(
    *,
    id: UUID | None = None,
    name: str = "Test Corp",
    ticker: str = "TEST",
    asset_class: AssetClass = AssetClass.EQUITY,
    currency: str = "USD",
    exchange: str = "NYSE",
    country: str = "US",
    sector: str | None = "Technology",
    industry: str | None = "Software",
    is_active: bool = True,
) -> Instrument:
    return Instrument(
        id=id or uuid4(),
        name=name,
        ticker=ticker,
        asset_class=asset_class,
        currency=currency,
        exchange=exchange,
        country=country,
        sector=sector,
        industry=industry,
        is_active=is_active,
    )


def make_price(
    *,
    instrument_id: str = "TEST",
    mid: Decimal = Decimal("100.00"),
    spread_bps: float = 10.0,
    timestamp: datetime | None = None,
    source: str = "test",
) -> PriceSnapshot:
    spread = mid * Decimal(str(spread_bps)) / Decimal("10000")
    half = spread / 2
    return PriceSnapshot(
        instrument_id=instrument_id,
        bid=mid - half,
        ask=mid + half,
        mid=mid,
        timestamp=timestamp or datetime.now(UTC),
        source=source,
    )


def make_trade(
    *,
    portfolio_id: UUID = DEFAULT_PORTFOLIO_ID,
    instrument_id: str = "AAPL",
    side: TradeSide = TradeSide.BUY,
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("150.00"),
    currency: str = "USD",
) -> TradeRequest:
    return TradeRequest(
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        price=price,
        currency=currency,
    )


def make_trade_event(
    *,
    portfolio_id: UUID = DEFAULT_PORTFOLIO_ID,
    instrument_id: str = "AAPL",
    side: TradeSide = TradeSide.BUY,
    quantity: str = "100",
    price: str = "150.00",
    trade_id: UUID | None = None,
    timestamp: datetime | None = None,
) -> TradeEvent:
    event_type = (
        PositionEventType.TRADE_BUY if side == TradeSide.BUY else PositionEventType.TRADE_SELL
    )
    return TradeEvent(
        event_type=event_type,
        timestamp=timestamp or datetime.now(UTC),
        data=TradeEventData(
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            side=side,
            quantity=Decimal(quantity),
            price=Decimal(price),
            trade_id=trade_id or uuid4(),
            currency="USD",
        ),
    )


# ---------------------------------------------------------------------------
# BaseEvent factories — for handler and cascade tests
# ---------------------------------------------------------------------------


def make_base_event(
    event_type: str = "trade.buy",
    data: dict | None = None,
    fund_slug: str = "alpha",
    actor_id: str = "test-user",
) -> BaseEvent:
    """Build a BaseEvent with sensible defaults."""
    return BaseEvent(
        event_type=event_type,
        data=data or {},
        fund_slug=fund_slug,
        actor_id=actor_id,
    )


def make_trades_executed_event(
    *,
    portfolio_id: UUID = DEFAULT_PORTFOLIO_ID,
    instrument_id: str = "AAPL",
    side: str = "buy",
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("150.00"),
    fund_slug: str = "alpha",
    trade_id: UUID | None = None,
) -> BaseEvent:
    """Build a trades.executed event matching what OrderService._process_fill publishes."""
    return BaseEvent(
        event_type=f"trade.{side}",
        data={
            "portfolio_id": str(portfolio_id),
            "instrument_id": instrument_id,
            "side": side,
            "quantity": str(quantity),
            "price": str(price),
            "trade_id": str(trade_id or uuid4()),
            "currency": "USD",
        },
        fund_slug=fund_slug,
        actor_id="test-user",
    )


def make_price_event(
    *,
    instrument_id: str = "AAPL",
    mid: Decimal = Decimal("155.00"),
    spread_bps: float = 10.0,
) -> BaseEvent:
    """Build a shared.prices.normalized event matching the price simulator."""
    spread = mid * Decimal(str(spread_bps)) / Decimal("10000")
    half = spread / 2
    return BaseEvent(
        event_type="price.updated",
        data={
            "instrument_id": instrument_id,
            "bid": str(mid - half),
            "ask": str(mid + half),
            "mid": str(mid),
            "volume": "10000",
            "source": "test",
        },
    )


def make_order_request(
    *,
    portfolio_id: UUID = DEFAULT_PORTFOLIO_ID,
    instrument_id: str = "AAPL",
    side: str = "buy",
    quantity: Decimal = Decimal("100"),
    limit_price: Decimal = Decimal("150.00"),
) -> CreateOrderRequest:
    """Build a CreateOrderRequest for order service tests."""
    return CreateOrderRequest(
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        side=OrderSide(side),
        order_type=OrderType.MARKET,
        quantity=quantity,
        limit_price=limit_price,
    )
