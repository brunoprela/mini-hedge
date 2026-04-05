"""Seed trades to populate positions for demo/development.

Run with:  uv run python -m app.seed_trades

Bypasses HTTP/auth and calls TradeHandler directly with a no-op event bus
so no Kafka connection is needed. The position read models are fully populated
in the database; the simulator's mark-to-market handler will price them once
the app starts.

Portfolio construction is designed to be compliant with the default seed
compliance rules:
  - Max single-name concentration: 5% of NAV  → ~20+ positions per portfolio
  - Max sector exposure: 25% of NAV           → diversified across 4+ sectors
  - Max country exposure: 40% of NAV          → mix of US and international
  - No short selling                          → all buys
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

BUY = TradeSide.BUY

# ==========================================================================
# ALPHA FUND — diversified long-only
# ==========================================================================

ALPHA_EQUITY_LS: list[SeedTrade] = [
    # Equity Long/Short — 26 positions, globally diversified, max ~4% per name
    # US Technology (~12%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "AAPL", BUY, "55", "190.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "MSFT", BUY, "25", "420.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "NVDA", BUY, "10", "880.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "META", BUY, "20", "510.00"),
    # US Consumer (~6%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "AMZN", BUY, "50", "185.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "DIS", BUY, "60", "105.00"),
    # US Financials (~6%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "JPM", BUY, "40", "200.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "V", BUY, "30", "280.00"),
    # US Healthcare (~5%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "JNJ", BUY, "45", "155.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "PFE", BUY, "200", "28.00"),
    # US Consumer Staples (~4%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "PG", BUY, "40", "165.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "KO", BUY, "80", "62.00"),
    # US Energy (~3%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "XOM", BUY, "35", "115.00"),
    # UK (~12%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "AZN", BUY, "65", "120.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "HSBA", BUY, "800", "7.50"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "SHEL", BUY, "200", "28.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "RIO", BUY, "80", "55.00"),
    # Europe (~12%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "SAP", BUY, "35", "195.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "ASML", BUY, "8", "900.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "TTE", BUY, "80", "58.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "NOVO.B", BUY, "50", "120.00"),
    # Japan (~4%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "7203", BUY, "200", "22.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "6758", BUY, "50", "85.00"),
    # Switzerland (~4%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "NESN", BUY, "50", "95.00"),
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "ROG", BUY, "20", "250.00"),
    # Other (~4%)
    ("alpha", PORTFOLIO_ALPHA_EQUITY_LS_ID, "BHP", BUY, "70", "60.00"),
]

ALPHA_GLOBAL_MACRO: list[SeedTrade] = [
    # Global Macro — 24 positions, tilted toward non-US, max ~4% per name
    # US (~28%)
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "XOM", BUY, "50", "115.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "JPM", BUY, "30", "200.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "JNJ", BUY, "35", "155.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "GOOGL", BUY, "25", "175.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "CVX", BUY, "30", "155.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "BRK.B", BUY, "12", "420.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "PG", BUY, "25", "165.00"),
    # UK (~12%)
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "SHEL", BUY, "150", "28.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "HSBA", BUY, "450", "7.50"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "BP", BUY, "600", "5.50"),
    # Europe (~16%)
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "TTE", BUY, "80", "58.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "SIE", BUY, "22", "180.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "MC", BUY, "5", "750.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "SAP", BUY, "20", "195.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "NOVO.B", BUY, "30", "120.00"),
    # Japan (~8%)
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "7203", BUY, "200", "22.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "6758", BUY, "40", "85.00"),
    # Switzerland (~6%)
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "NESN", BUY, "40", "95.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "NOVN", BUY, "35", "88.00"),
    # Other (~12%)
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "BHP", BUY, "60", "60.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "RY", BUY, "30", "110.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "005930", BUY, "60", "55.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "VALE3", BUY, "200", "12.00"),
    ("alpha", PORTFOLIO_ALPHA_GLOBAL_MACRO_ID, "2330", BUY, "150", "22.00"),
]

ALPHA_TRADES = ALPHA_EQUITY_LS + ALPHA_GLOBAL_MACRO

# ==========================================================================
# BETA FUND — quant strategies, diversified
# ==========================================================================

BETA_STAT_ARB: list[SeedTrade] = [
    # Stat Arb — 26 positions, tech-heavy but well diversified, max ~4% per name
    # US Tech (~16%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "AAPL", BUY, "35", "190.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "MSFT", BUY, "15", "420.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "GOOGL", BUY, "30", "175.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "NVDA", BUY, "6", "880.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "META", BUY, "10", "510.00"),
    # US Consumer (~6%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "AMZN", BUY, "25", "185.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "TSLA", BUY, "20", "175.00"),
    # US Financials (~6%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "JPM", BUY, "20", "200.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "GS", BUY, "6", "470.00"),
    # US Healthcare (~6%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "UNH", BUY, "6", "525.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "JNJ", BUY, "20", "155.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "PFE", BUY, "100", "28.00"),
    # UK (~10%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "AZN", BUY, "35", "120.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "SHEL", BUY, "100", "28.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "ULVR", BUY, "80", "42.00"),
    # Europe (~12%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "SAP", BUY, "20", "195.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "SIE", BUY, "18", "180.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "ASML", BUY, "4", "900.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "TTE", BUY, "45", "58.00"),
    # Japan (~4%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "7203", BUY, "120", "22.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "6758", BUY, "25", "85.00"),
    # Switzerland (~4%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "NESN", BUY, "30", "95.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "ROG", BUY, "12", "250.00"),
    # Other (~8%)
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "005930", BUY, "40", "55.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "BHP", BUY, "40", "60.00"),
    ("beta", PORTFOLIO_BETA_STAT_ARB_ID, "9988", BUY, "200", "10.00"),
]

BETA_MOMENTUM: list[SeedTrade] = [
    # Momentum — 24 positions, higher-beta names globally, max ~4% per name
    # US Tech (~12%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "NVDA", BUY, "8", "880.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "MSFT", BUY, "15", "420.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "META", BUY, "12", "510.00"),
    # US Consumer (~8%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "AMZN", BUY, "25", "185.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "TSLA", BUY, "25", "175.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "DIS", BUY, "40", "105.00"),
    # US Financials (~6%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "GS", BUY, "6", "470.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "V", BUY, "15", "280.00"),
    # US Healthcare (~4%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "UNH", BUY, "6", "525.00"),
    # US Energy (~4%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "XOM", BUY, "20", "115.00"),
    # US Consumer Staples (~3%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "KO", BUY, "50", "62.00"),
    # UK (~10%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "AZN", BUY, "30", "120.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "HSBA", BUY, "350", "7.50"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "RIO", BUY, "40", "55.00"),
    # Europe (~12%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "SAP", BUY, "18", "195.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "MC", BUY, "5", "750.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "NOVO.B", BUY, "25", "120.00"),
    # Japan (~6%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "6758", BUY, "35", "85.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "7203", BUY, "150", "22.00"),
    # Switzerland (~4%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "NOVN", BUY, "25", "88.00"),
    # Other (~8%)
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "005930", BUY, "45", "55.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "BHP", BUY, "30", "60.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "RY", BUY, "20", "110.00"),
    ("beta", PORTFOLIO_BETA_MOMENTUM_ID, "2330", BUY, "100", "22.00"),
]

BETA_MARKET_NEUTRAL: list[SeedTrade] = [
    # Market Neutral — 24 positions, balanced sectors, max ~4% per name
    # US Tech (~8%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "GOOGL", BUY, "18", "175.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "AAPL", BUY, "15", "190.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "META", BUY, "6", "510.00"),
    # US Consumer (~6%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "AMZN", BUY, "12", "185.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "DIS", BUY, "25", "105.00"),
    # US Financials (~8%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "JPM", BUY, "15", "200.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "BRK.B", BUY, "6", "420.00"),
    # US Healthcare (~8%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "JNJ", BUY, "18", "155.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "UNH", BUY, "5", "525.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "PFE", BUY, "80", "28.00"),
    # US Energy (~4%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "CVX", BUY, "15", "155.00"),
    # UK (~12%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "SHEL", BUY, "90", "28.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "AZN", BUY, "22", "120.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "ULVR", BUY, "60", "42.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "BP", BUY, "400", "5.50"),
    # Europe (~12%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "TTE", BUY, "35", "58.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "SIE", BUY, "12", "180.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "SAP", BUY, "12", "195.00"),
    # Japan (~6%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "7203", BUY, "90", "22.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "6758", BUY, "22", "85.00"),
    # Switzerland (~6%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "NESN", BUY, "20", "95.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "NOVN", BUY, "20", "88.00"),
    # Other (~6%)
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "BHP", BUY, "22", "60.00"),
    ("beta", PORTFOLIO_BETA_MARKET_NEUTRAL_ID, "RY", BUY, "12", "110.00"),
]

BETA_TRADES = BETA_STAT_ARB + BETA_MOMENTUM + BETA_MARKET_NEUTRAL

# ==========================================================================
# GAMMA FUND — thematic but diversified
# ==========================================================================

GAMMA_EVENT_DRIVEN: list[SeedTrade] = [
    # Event-Driven — 24 positions, catalyst plays globally, max ~4% per name
    # US Tech (~12%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "MSFT", BUY, "14", "420.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "GOOGL", BUY, "22", "175.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "NVDA", BUY, "5", "880.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "META", BUY, "8", "510.00"),
    # US Consumer (~6%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "AMZN", BUY, "18", "185.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "TSLA", BUY, "15", "175.00"),
    # US Financials (~6%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "JPM", BUY, "15", "200.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "V", BUY, "12", "280.00"),
    # US Healthcare (~4%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "UNH", BUY, "4", "525.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "PFE", BUY, "100", "28.00"),
    # UK (~10%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "AZN", BUY, "28", "120.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "HSBA", BUY, "350", "7.50"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "SHEL", BUY, "80", "28.00"),
    # Europe (~12%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "MC", BUY, "4", "750.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "SAP", BUY, "15", "195.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "TTE", BUY, "45", "58.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "ASML", BUY, "3", "900.00"),
    # Japan (~4%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "6758", BUY, "20", "85.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "7203", BUY, "80", "22.00"),
    # Switzerland (~6%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "NESN", BUY, "22", "95.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "NOVN", BUY, "22", "88.00"),
    # Other (~8%)
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "005930", BUY, "30", "55.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "BHP", BUY, "30", "60.00"),
    ("gamma", PORTFOLIO_GAMMA_EVENT_DRIVEN_ID, "RY", BUY, "15", "110.00"),
]

GAMMA_DISTRESSED: list[SeedTrade] = [
    # Distressed/Value — 24 positions, value-oriented globally, max ~4% per name
    # US Financials (~8%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "JPM", BUY, "18", "200.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "GS", BUY, "6", "470.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "BRK.B", BUY, "6", "420.00"),
    # US Energy (~6%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "XOM", BUY, "22", "115.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "CVX", BUY, "15", "155.00"),
    # US Healthcare (~6%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "JNJ", BUY, "15", "155.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "PFE", BUY, "100", "28.00"),
    # US Tech (~6%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "AAPL", BUY, "12", "190.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "MSFT", BUY, "5", "420.00"),
    # US Consumer Staples (~4%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "KO", BUY, "40", "62.00"),
    # UK (~12%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "HSBA", BUY, "350", "7.50"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "SHEL", BUY, "100", "28.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "AZN", BUY, "22", "120.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "ULVR", BUY, "60", "42.00"),
    # Europe (~12%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "SIE", BUY, "15", "180.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "TTE", BUY, "45", "58.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "MC", BUY, "3", "750.00"),
    # Japan (~6%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "7203", BUY, "90", "22.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "6758", BUY, "20", "85.00"),
    # Switzerland (~6%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "NESN", BUY, "20", "95.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "NOVN", BUY, "20", "88.00"),
    # Other (~8%)
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "BHP", BUY, "35", "60.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "RY", BUY, "15", "110.00"),
    ("gamma", PORTFOLIO_GAMMA_DISTRESSED_ID, "VALE3", BUY, "150", "12.00"),
]

GAMMA_TRADES = GAMMA_EVENT_DRIVEN + GAMMA_DISTRESSED

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
    request_context = RequestContext(
        actor_id=USER_ADMIN_ID,
        actor_type=ActorType.SYSTEM,
        fund_slug="alpha",
        fund_id=FUND_ALPHA_ID,
    )
    set_request_context(request_context)
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
            request_context=trade_ctx,
            portfolio_id=UUID(portfolio_id),
            instrument_id=instrument_id,
            side=side,
            quantity=Decimal(qty),
            price=Decimal(price),
        )
        label = f"{side.value.upper():4s} {qty:>5s} {instrument_id:<7s} @ {price:>8s}"
        print(f"  {label}  [{fund_slug}]")

    print(f"\nDone — {len(ALL_TRADES)} trades executed, positions populated.")
    print("Start the app to see prices update via the simulator.")


if __name__ == "__main__":
    asyncio.run(main())
