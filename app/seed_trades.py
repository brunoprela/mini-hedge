"""Seed trades to populate positions for demo/development.

Run with:  uv run python -m app.seed_trades

Bypasses HTTP/auth and calls TradeHandler directly with a no-op event bus
so no Kafka connection is needed. The position read models are fully populated
in the database; the simulator's mark-to-market handler will price them once
the app starts.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID

import structlog

from app.config import get_settings
from app.modules.platform.seed import (
    FUND_ALPHA_ID,
    FUND_BETA_ID,
    FUND_GAMMA_ID,
    PORTFOLIO_ALPHA_EQUITY_LS_ID,
    PORTFOLIO_ALPHA_GLOBAL_MACRO_ID,
    PORTFOLIO_BETA_MARKET_NEUTRAL_ID,
    PORTFOLIO_BETA_MOMENTUM_ID,
    PORTFOLIO_BETA_STAT_ARB_ID,
    PORTFOLIO_GAMMA_DISTRESSED_ID,
    PORTFOLIO_GAMMA_EVENT_DRIVEN_ID,
    USER_ADMIN_ID,
    USER_ALPHA_PM_ID,
    USER_BETA_PM_ID,
    USER_GAMMA_PM_ID,
)
from app.modules.positions.event_store import EventStoreRepository
from app.modules.positions.interface import TradeSide
from app.modules.positions.position_projector import PositionProjector
from app.modules.positions.position_repository import CurrentPositionRepository
from app.modules.positions.trade_handler import TradeHandler
from app.shared.database import build_engine
from app.shared.events import InProcessEventBus
from app.shared.logging import setup_logging
from app.shared.request_context import ActorType, RequestContext, set_request_context

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Seed trade definitions
# ---------------------------------------------------------------------------

SeedTrade = tuple[str, str, str, TradeSide, str, str]
# (fund_slug, portfolio_id, instrument_id, side, quantity, price)

ALPHA_TRADES: list[SeedTrade] = [
    # Equity Long/Short — tech longs, bank short
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "AAPL", TradeSide.BUY, "500", "185.50"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "MSFT", TradeSide.BUY, "300", "420.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "NVDA", TradeSide.BUY, "200", "875.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "GOOGL", TradeSide.BUY, "400", "175.25"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "JPM", TradeSide.BUY, "350", "195.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "TSLA", TradeSide.BUY, "150", "245.00"),
    # Global Macro — broad exposure
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "XOM", TradeSide.BUY, "600", "105.75"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "GS", TradeSide.BUY, "200", "385.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "JNJ", TradeSide.BUY, "400", "155.50"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "AMZN", TradeSide.BUY, "250", "185.00"),
]

BETA_TRADES: list[SeedTrade] = [
    # Stat Arb — paired positions
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "AAPL", TradeSide.BUY, "300", "184.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "MSFT", TradeSide.BUY, "200", "418.50"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "GOOGL", TradeSide.BUY, "350", "174.00"),
    # Momentum — high-beta names
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "NVDA", TradeSide.BUY, "400", "870.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "TSLA", TradeSide.BUY, "500", "242.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "AMZN", TradeSide.BUY, "300", "183.50"),
    # Market Neutral — balanced long/short
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "AAPL", TradeSide.BUY, "200", "185.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "JNJ", TradeSide.BUY, "300", "154.75"),
]

GAMMA_TRADES: list[SeedTrade] = [
    # Event-Driven — catalyst plays
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "AMZN", TradeSide.BUY, "350", "184.25"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "GOOGL", TradeSide.BUY, "500", "173.50"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "MSFT", TradeSide.BUY, "250", "419.00"),
    # Distressed — value plays
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "XOM", TradeSide.BUY, "800", "104.50"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "JPM", TradeSide.BUY, "400", "193.50"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "GS", TradeSide.BUY, "150", "382.00"),
]

ALL_TRADES = ALPHA_TRADES + BETA_TRADES + GAMMA_TRADES

FUND_SLUG_TO_ID = {
    "alpha": FUND_ALPHA_ID,
    "beta": FUND_BETA_ID,
    "gamma": FUND_GAMMA_ID,
}

FUND_SLUG_TO_ACTOR = {
    "alpha": USER_ALPHA_PM_ID,
    "beta": USER_BETA_PM_ID,
    "gamma": USER_GAMMA_PM_ID,
}


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    _, session_factory = build_engine()

    # Use a no-op event bus — we only want database side-effects
    event_bus = InProcessEventBus()

    event_store = EventStoreRepository(session_factory)
    position_repo = CurrentPositionRepository(session_factory)
    projector = PositionProjector(position_repo)
    trade_handler = TradeHandler(session_factory, event_store, projector, event_bus)

    # Check if trades already exist (idempotent)
    ctx = RequestContext(
        actor_id=USER_ADMIN_ID,
        actor_type=ActorType.SYSTEM,
        fund_slug="alpha",
        fund_id=FUND_ALPHA_ID,
    )
    set_request_context(ctx)
    existing = await position_repo.get_by_portfolio(UUID(PORTFOLIO_ALPHA_EQUITY_LS_ID))
    if existing:
        print(f"Already have {len(existing)} positions in Alpha Equity L/S, skipping seed trades.")
        return

    print(f"Seeding {len(ALL_TRADES)} trades across 3 funds...")

    for fund_slug, portfolio_id, instrument_id, side, qty, price in ALL_TRADES:
        # Set request context for the fund so schema translation works
        trade_ctx = RequestContext(
            actor_id=FUND_SLUG_TO_ACTOR[fund_slug],
            actor_type=ActorType.SYSTEM,
            fund_slug=fund_slug,
            fund_id=FUND_SLUG_TO_ID[fund_slug],
        )
        set_request_context(trade_ctx)

        await trade_handler.handle_trade(
            ctx=trade_ctx,
            portfolio_id=UUID(portfolio_id),
            instrument_id=instrument_id,
            side=side,
            quantity=Decimal(qty),
            price=Decimal(price),
        )
        label = f"{side.value.upper():4s} {qty:>5s} {instrument_id:<5s} @ {price:>8s}"
        print(f"  {label}  [{fund_slug}]")

    print(f"\nDone — {len(ALL_TRADES)} trades executed, positions populated.")
    print("Start the app to see prices update via the simulator.")


if __name__ == "__main__":
    asyncio.run(main())
