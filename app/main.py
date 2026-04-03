"""FastAPI application entry point — wires modules, starts simulator, health check."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, Request, Response
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus
    from app.shared.types import AssetClass

from app.config import get_settings
from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.repository import PriceRepository
from app.modules.market_data.routes import router as market_data_router
from app.modules.market_data.service import MarketDataService
from app.modules.market_data.simulator import MarketDataSimulator
from app.modules.platform.auth_service import AuthService
from app.modules.platform.repository import (
    APIKeyRepository,
    FundMembershipRepository,
    FundRepository,
    PortfolioRepository,
    UserRepository,
)
from app.modules.platform.routes import router as platform_router
from app.modules.platform.seed import (
    DEV_API_KEY,
    build_seed_api_keys,
    build_seed_funds,
    build_seed_memberships,
    build_seed_portfolios,
    build_seed_users,
)
from app.modules.positions.event_store import EventStoreRepository
from app.modules.positions.mtm_handler import MarkToMarketHandler
from app.modules.positions.position_projector import PositionProjector
from app.modules.positions.position_repository import CurrentPositionRepository
from app.modules.positions.routes import router as positions_router
from app.modules.positions.service import PositionService
from app.modules.positions.trade_handler import TradeHandler
from app.modules.realtime.routes import router as realtime_router
from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.routes import router as security_master_router
from app.modules.security_master.seed import build_seed_records
from app.modules.security_master.service import SecurityMasterService
from app.shared.database import build_engine
from app.shared.fund_schema import ensure_all_fund_schemas
from app.shared.logging import setup_logging
from app.shared.request_context import set_request_context
from app.shared.schema_registry import fund_topics_for_slug, shared_topic, shared_topics

logger = structlog.get_logger()

# Bounded contexts whose Alembic migrations run on startup.
# Positions are NOT here — each fund gets its own schema, created
# by ensure_all_fund_schemas() after platform seeding discovers active funds.
MIGRATION_CONTEXTS = ["platform", "security_master", "market_data"]

# Paths that skip authentication
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/api/v1/stream/events"}


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseHTTPMiddleware):
    """Extracts identity from Authorization header and sets RequestContext.

    Looks up ``auth_service`` from ``request.app.state`` so it can be
    registered at module level (before the lifespan runs).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip auth for public endpoints
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # /auth/agent-token requires auth via its own dependency.

        auth_service: AuthService | None = getattr(request.app.state, "auth_service", None)
        if auth_service is None:
            return Response(
                content='{"detail":"Auth service unavailable"}',
                status_code=503,
                media_type="application/json",
            )

        ctx = await self._resolve_context(request, auth_service)
        if ctx is None:
            return Response(
                content='{"detail":"Authentication required"}',
                status_code=401,
                media_type="application/json",
            )

        set_request_context(ctx)
        return await call_next(request)

    async def _resolve_context(self, request: Request, auth: AuthService):  # type: ignore[no-untyped-def]
        auth_header = request.headers.get("authorization", "")
        fund_slug = request.headers.get("x-fund-slug")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return await auth.authenticate_jwt(token, fund_slug=fund_slug)

        if auth_header.startswith("ApiKey "):
            raw_key = auth_header[7:]
            return await auth.authenticate_api_key(raw_key)

        # Also check X-API-Key header
        api_key = request.headers.get("x-api-key")
        if api_key:
            return await auth.authenticate_api_key(api_key)

        return None


# ---------------------------------------------------------------------------
# Migrations and seeding
# ---------------------------------------------------------------------------


def _run_migrations_sync() -> None:
    for ctx in MIGRATION_CONTEXTS:
        cfg = AlembicConfig("alembic.ini", ini_section=ctx)
        cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
        alembic_command.upgrade(cfg, "head")
        logger.info("migrations_applied", context=ctx)


async def _run_migrations() -> None:
    await asyncio.to_thread(_run_migrations_sync)


async def _seed_instruments(repo: InstrumentRepository) -> None:
    existing = await repo.get_all_active()
    if not existing:
        instruments, extensions = build_seed_records()
        await repo.insert_batch(instruments, extensions)
        logger.info("instruments_seeded", count=len(instruments), extensions=len(extensions))


async def _seed_platform(
    fund_repo: FundRepository,
    portfolio_repo: PortfolioRepository,
    user_repo: UserRepository,
    membership_repo: FundMembershipRepository,
    api_key_repo: APIKeyRepository,
) -> None:
    """Seed funds, portfolios, users, memberships, and API keys."""
    existing_funds = await fund_repo.get_all_active()
    if not existing_funds:
        funds = build_seed_funds()
        for fund in funds:
            await fund_repo.insert(fund)
        portfolios = build_seed_portfolios()
        await portfolio_repo.insert_batch(portfolios)
        logger.info(
            "platform_seeded",
            funds=len(funds),
            portfolios=len(portfolios),
        )

    existing_users = await user_repo.get_all_active()
    if not existing_users:
        users = build_seed_users()
        for user in users:
            await user_repo.insert(user)
        memberships = build_seed_memberships()
        for membership in memberships:
            await membership_repo.insert(membership)
        api_keys = build_seed_api_keys()
        for api_key in api_keys:
            await api_key_repo.insert(api_key)
        logger.info(
            "auth_seeded",
            users=len(users),
            api_key=DEV_API_KEY,
        )


# ---------------------------------------------------------------------------
# Per-module setup helpers (called from lifespan)
# ---------------------------------------------------------------------------


async def _setup_platform(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    settings: object,
) -> tuple[AuthService, FundRepository]:
    """Wire platform module: repos, seeding, FGA, auth service."""
    fund_repo = FundRepository(session_factory)
    portfolio_repo = PortfolioRepository(session_factory)
    user_repo = UserRepository(session_factory)
    membership_repo = FundMembershipRepository(session_factory)
    api_key_repo = APIKeyRepository(session_factory)

    await _seed_platform(fund_repo, portfolio_repo, user_repo, membership_repo, api_key_repo)

    auth_service = AuthService(
        user_repo=user_repo,
        fund_repo=fund_repo,
        membership_repo=membership_repo,
        api_key_repo=api_key_repo,
        jwt_secret=settings.jwt_secret,  # type: ignore[attr-defined]
        jwt_algorithm=settings.jwt_algorithm,  # type: ignore[attr-defined]
        jwt_expiry_minutes=settings.jwt_expiry_minutes,  # type: ignore[attr-defined]
        keycloak_url=settings.keycloak_url,  # type: ignore[attr-defined]
        keycloak_browser_url=settings.keycloak_browser_url,  # type: ignore[attr-defined]
        keycloak_realm=settings.keycloak_realm,  # type: ignore[attr-defined]
        keycloak_client_id=settings.keycloak_client_id,  # type: ignore[attr-defined]
    )
    fastapi_app.state.auth_service = auth_service
    fastapi_app.state.portfolio_repo = portfolio_repo
    return auth_service, fund_repo


async def _setup_fga(fastapi_app: FastAPI, settings: object) -> object | None:
    """Initialize OpenFGA if enabled. Returns the FGA client or None."""
    if not settings.fga_enabled:  # type: ignore[attr-defined]
        return None

    import app.shared.fga_resources  # noqa: F401 — triggers resource type registration
    from app.modules.platform.seed import build_seed_fga_tuples
    from app.shared.fga import initialize_fga

    fga_client = await initialize_fga(
        api_url=settings.fga_api_url,  # type: ignore[attr-defined]
        store_name=settings.fga_store_name,  # type: ignore[attr-defined]
    )
    fastapi_app.state.fga = fga_client
    tuples = build_seed_fga_tuples()
    await fga_client.write_tuples(tuples)
    logger.info("fga_tuples_seeded", count=len(tuples))
    return fga_client


async def _setup_security_master(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
) -> None:
    """Wire security master module: repo, service, seeding."""
    instrument_repo = InstrumentRepository(session_factory)
    fastapi_app.state.security_master_service = SecurityMasterService(instrument_repo)
    await _seed_instruments(instrument_repo)


def _setup_market_data(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    event_bus: EventBus,
) -> MarketDataService:
    """Wire market data module: repo, service, price event handler."""
    price_repo = PriceRepository(session_factory)
    market_data_service = MarketDataService(price_repo)
    fastapi_app.state.market_data_service = market_data_service

    event_bus.subscribe(shared_topic("prices.normalized"), _make_price_handler(market_data_service))
    return market_data_service


def _setup_positions(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    event_bus: EventBus,
    fund_repo: FundRepository,
    security_master_service: SecurityMasterService,
) -> None:
    """Wire positions module: repos, projector, handlers, service, MTM subscription."""
    event_store_repo = EventStoreRepository(session_factory)
    position_repo = CurrentPositionRepository(session_factory)
    projector = PositionProjector(position_repo)
    trade_handler = TradeHandler(session_factory, event_store_repo, projector, event_bus)
    fastapi_app.state.position_service = PositionService(position_repo, trade_handler)

    async def get_fund_slugs() -> list[str]:
        funds = await fund_repo.get_all_active()
        return [f.slug for f in funds]

    async def get_asset_class(instrument_id: str) -> AssetClass | None:
        try:
            instrument = await security_master_service.get_by_ticker(instrument_id)
        except Exception:
            return None
        return instrument.asset_class

    mtm_handler = MarkToMarketHandler(session_factory, event_bus, get_fund_slugs, get_asset_class)
    event_bus.subscribe(shared_topic("prices.normalized"), mtm_handler.handle_price_update)


# ---------------------------------------------------------------------------
# Event handlers (extracted from lifespan)
# ---------------------------------------------------------------------------


def _make_price_handler(market_data_service: MarketDataService):  # type: ignore[no-untyped-def]
    """Create a price event handler bound to the given service."""

    async def on_price_event(event: BaseEvent) -> None:
        raw_volume = event.data.get("volume")
        snapshot = PriceSnapshot(
            instrument_id=event.data["instrument_id"],
            bid=Decimal(event.data["bid"]),
            ask=Decimal(event.data["ask"]),
            mid=Decimal(event.data["mid"]),
            volume=Decimal(raw_volume) if raw_volume is not None else None,
            timestamp=event.timestamp,
            source=event.data["source"],
        )
        market_data_service.update_latest(snapshot)
        await market_data_service.store_price(snapshot)

    return on_price_event


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Database
    engine, session_factory = build_engine()

    # Run migrations in thread pool (env.py uses sync psycopg2 to avoid
    # asyncio.run() conflicts with uvloop under uvicorn)
    await _run_migrations()

    # Configure structlog after migrations — Alembic's fileConfig creates
    # a root stderr handler that we reuse with structlog's formatter.
    setup_logging(settings.log_level)

    # Event bus — always Kafka
    from app.shared.kafka import KafkaEventBus
    from app.shared.schema_registry import load_schemas, register_schemas

    load_schemas()
    register_schemas(settings.kafka_schema_registry_url)

    kafka_bus = KafkaEventBus(
        settings.kafka_bootstrap_servers,
        consumer_group="minihedge",
    )
    event_bus: EventBus = kafka_bus

    # --- Module setup ---
    auth_service, fund_repo = await _setup_platform(fastapi_app, session_factory, settings)
    fga_client = await _setup_fga(fastapi_app, settings)
    await _setup_security_master(fastapi_app, session_factory)

    # Create per-fund schemas and run positions migrations for each
    active_funds = await fund_repo.get_all_active()
    fund_slugs = [f.slug for f in active_funds]
    await ensure_all_fund_schemas(engine, fund_slugs)

    # Create Kafka topics — shared + per-fund + DLQ
    all_topics = shared_topics()
    for slug in fund_slugs:
        all_topics.extend(fund_topics_for_slug(slug))
    dlq_topics = [f"{t}.dlq" for t in all_topics]
    kafka_bus.ensure_topics(all_topics + dlq_topics)

    _setup_market_data(fastapi_app, session_factory, event_bus)
    sm_service: SecurityMasterService = fastapi_app.state.security_master_service
    _setup_positions(fastapi_app, session_factory, event_bus, fund_repo, sm_service)

    # Redis — bridge event bus to pub/sub for SSE streaming
    redis_client = None
    if settings.redis_enabled:
        from app.shared.redis import create_redis_client
        from app.shared.redis_bridge import RedisBridge

        redis_client = await create_redis_client(settings.redis_url)
        fastapi_app.state.redis = redis_client
        bridge = RedisBridge(redis_client)
        bridge.wire(event_bus, fund_slugs)

    # Start Kafka consumers (after all subscriptions are registered)
    await kafka_bus.start()

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
    fastapi_app.state.engine = engine
    fastapi_app.state.kafka_bus = kafka_bus

    logger.info("app_started", env=settings.app_env, simulator=settings.simulator_enabled)

    yield

    # Shutdown
    if simulator is not None:
        simulator.stop()
    if simulator_task is not None:
        simulator_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await simulator_task

    await kafka_bus.stop()

    if redis_client is not None:
        await redis_client.aclose()

    if fga_client is not None:
        await fga_client.close()

    await engine.dispose()
    logger.info("app_stopped")


app = FastAPI(
    title="Mini Hedge Fund Desk",
    version="0.1.0",
    lifespan=lifespan,
)

# Auth middleware — registered at module level; looks up auth_service from app.state
app.add_middleware(AuthMiddleware)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return Response(
        content='{"detail":"Internal server error"}',
        status_code=500,
        media_type="application/json",
    )


# Register routers
app.include_router(platform_router, prefix="/api/v1")
app.include_router(security_master_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")
app.include_router(positions_router, prefix="/api/v1")
app.include_router(realtime_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, object]:
    """Readiness probe — checks PostgreSQL, Redis, and Kafka connectivity."""
    components: dict[str, str] = {}

    # PostgreSQL
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components["postgres"] = "healthy"
    except Exception as e:
        components["postgres"] = f"unhealthy: {e}"

    # Redis (if enabled)
    redis = getattr(app.state, "redis", None)
    if redis is not None:
        try:
            await redis.ping()
            components["redis"] = "healthy"
        except Exception as e:
            components["redis"] = f"unhealthy: {e}"

    # Kafka
    try:
        app.state.kafka_bus._producer.flush(timeout=2.0)
        components["kafka"] = "healthy"
    except Exception as e:
        components["kafka"] = f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in components.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
    }
