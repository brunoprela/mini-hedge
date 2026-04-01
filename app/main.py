"""FastAPI application entry point — wires modules, starts simulator, health check."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings

# Module imports
from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.repository import PriceRepository
from app.modules.market_data.routes import init_routes as init_market_data_routes
from app.modules.market_data.routes import router as market_data_router
from app.modules.market_data.service import MarketDataService
from app.modules.market_data.simulator import MarketDataSimulator
from app.modules.platform.repository import FundRepository, PortfolioRepository
from app.modules.platform.seed import build_seed_fund, build_seed_portfolios
from app.modules.positions.handlers import MarkToMarketHandler, TradeHandler
from app.modules.positions.repository import CurrentPositionRepository, EventStoreRepository
from app.modules.positions.routes import init_routes as init_position_routes
from app.modules.positions.routes import router as positions_router
from app.modules.positions.service import PositionService
from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.routes import init_routes as init_security_master_routes
from app.modules.security_master.routes import router as security_master_router
from app.modules.security_master.seed import build_seed_records
from app.modules.security_master.service import SecurityMasterService
from app.shared.database import build_engine
from app.shared.events import InProcessEventBus
from app.shared.fund_context import DEFAULT_FUND_SLUG, set_current_fund
from app.shared.logging import setup_logging

logger = structlog.get_logger()

# Bounded contexts whose Alembic migrations run on startup.
# Each name corresponds to a section in alembic.ini.
MIGRATION_CONTEXTS = ["platform", "security_master", "market_data", "positions"]


def _run_migrations_sync() -> None:
    """Run Alembic migrations for every bounded context.

    Uses Alembic's programmatic API so each context gets its own
    migration history (alembic_version table scoped to its schema).
    """
    for ctx in MIGRATION_CONTEXTS:
        cfg = AlembicConfig("alembic.ini", ini_section=ctx)
        cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
        alembic_command.upgrade(cfg, "head")
        logger.info("migrations_applied", context=ctx)


async def _run_migrations() -> None:
    """Run Alembic migrations in a thread to avoid event-loop conflicts.

    Each module's env.py calls asyncio.run() internally, which requires
    its own event loop. Running in a thread avoids conflicting with
    the already-running uvicorn loop.
    """
    await asyncio.to_thread(_run_migrations_sync)


async def _seed_instruments(repo: InstrumentRepository) -> None:
    """Seed instruments and equity extensions if the table is empty."""
    existing = await repo.get_all_active()
    if not existing:
        instruments, extensions = build_seed_records()
        await repo.insert_batch(instruments)
        await repo.insert_batch_extensions(extensions)
        logger.info("instruments_seeded", count=len(instruments), extensions=len(extensions))


async def _seed_platform(
    fund_repo: FundRepository,
    portfolio_repo: PortfolioRepository,
) -> None:
    """Seed default fund and portfolios if none exist."""
    existing = await fund_repo.get_all_active()
    if not existing:
        fund = build_seed_fund()
        await fund_repo.insert(fund)
        portfolios = build_seed_portfolios()
        await portfolio_repo.insert_batch(portfolios)
        logger.info("platform_seeded", fund=fund.slug, portfolios=len(portfolios))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.log_level)

    # Database
    engine, session_factory = build_engine()

    # Run migrations
    await _run_migrations()

    # Event bus
    event_bus = InProcessEventBus()

    # Set default fund context (single-fund Phase 0)
    set_current_fund(DEFAULT_FUND_SLUG)

    # --- Platform ---
    fund_repo = FundRepository(session_factory)
    portfolio_repo = PortfolioRepository(session_factory)
    await _seed_platform(fund_repo, portfolio_repo)

    # --- Security Master ---
    instrument_repo = InstrumentRepository(session_factory)
    security_master_service = SecurityMasterService(instrument_repo)
    init_security_master_routes(security_master_service)
    await _seed_instruments(instrument_repo)

    # --- Market Data ---
    price_repo = PriceRepository(session_factory)
    market_data_service = MarketDataService(price_repo)
    init_market_data_routes(market_data_service)

    # Wire: price events update in-memory cache and persist to DB
    async def on_price_event(event):  # type: ignore[no-untyped-def]
        from decimal import Decimal

        snapshot = PriceSnapshot(
            instrument_id=event.data["instrument_id"],
            bid=Decimal(event.data["bid"]),
            ask=Decimal(event.data["ask"]),
            mid=Decimal(event.data["mid"]),
            timestamp=event.timestamp,
            source=event.data["source"],
        )
        market_data_service.update_latest(snapshot)
        await market_data_service.store_price(snapshot)

    event_bus.subscribe("prices.normalized", on_price_event)

    # --- Positions ---
    event_store_repo = EventStoreRepository(session_factory)
    position_repo = CurrentPositionRepository(session_factory)
    trade_handler = TradeHandler(event_store_repo, position_repo, event_bus)
    position_service = PositionService(position_repo, trade_handler)
    init_position_routes(position_service)

    # Wire: price events trigger mark-to-market
    mtm_handler = MarkToMarketHandler(position_repo, event_bus)
    event_bus.subscribe("prices.normalized", mtm_handler.handle_price_update)

    # --- Simulator ---
    simulator_task: asyncio.Task | None = None  # type: ignore[type-arg]
    simulator: MarketDataSimulator | None = None
    if settings.simulator_enabled:
        simulator = MarketDataSimulator(
            event_bus=event_bus,
            interval_ms=settings.simulator_interval_ms,
        )
        simulator_task = asyncio.create_task(simulator.run())

    # Store references for health check
    app.state.engine = engine

    logger.info("app_started", env=settings.app_env, simulator=settings.simulator_enabled)

    yield

    # Shutdown
    if simulator is not None:
        simulator.stop()
    if simulator_task is not None:
        simulator_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await simulator_task

    await engine.dispose()
    logger.info("app_stopped")


app = FastAPI(
    title="Mini Hedge Fund Desk",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(security_master_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")
app.include_router(positions_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Readiness probe — checks PostgreSQL connectivity."""
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}
