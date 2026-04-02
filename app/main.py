"""FastAPI application entry point — wires modules, starts simulator, health check."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings

# Module imports
from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.repository import PriceRepository
from app.modules.market_data.routes import init_routes as init_market_data_routes
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
from app.modules.platform.seed import (
    DEV_API_KEY,
    build_seed_api_key,
    build_seed_fund,
    build_seed_membership,
    build_seed_portfolios,
    build_seed_user,
)
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
from app.shared.logging import setup_logging
from app.shared.request_context import ActorType, set_request_context

logger = structlog.get_logger()

# Bounded contexts whose Alembic migrations run on startup.
MIGRATION_CONTEXTS = ["platform", "security_master", "market_data", "positions"]

# Paths that skip authentication
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


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

        # Allow /auth/* endpoints without auth (they issue tokens)
        if request.url.path.startswith("/auth/"):
            return await call_next(request)

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

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return await auth.authenticate_jwt(token)

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
        await repo.insert_batch(instruments)
        await repo.insert_batch_extensions(extensions)
        logger.info("instruments_seeded", count=len(instruments), extensions=len(extensions))


async def _seed_platform(
    fund_repo: FundRepository,
    portfolio_repo: PortfolioRepository,
    user_repo: UserRepository,
    membership_repo: FundMembershipRepository,
    api_key_repo: APIKeyRepository,
) -> None:
    """Seed default fund, portfolios, user, membership, and API key."""
    existing_funds = await fund_repo.get_all_active()
    if not existing_funds:
        fund = build_seed_fund()
        await fund_repo.insert(fund)
        portfolios = build_seed_portfolios()
        await portfolio_repo.insert_batch(portfolios)
        logger.info("platform_seeded", fund=fund.slug, portfolios=len(portfolios))

    existing_users = await user_repo.get_all_active()
    if not existing_users:
        user = build_seed_user()
        await user_repo.insert(user)
        membership = build_seed_membership()
        await membership_repo.insert(membership)
        api_key = build_seed_api_key()
        await api_key_repo.insert(api_key)
        logger.info(
            "auth_seeded",
            user=user.email,
            api_key=DEV_API_KEY,
        )


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

    # Event bus
    event_bus = InProcessEventBus()

    # --- Platform ---
    fund_repo = FundRepository(session_factory)
    portfolio_repo = PortfolioRepository(session_factory)
    user_repo = UserRepository(session_factory)
    membership_repo = FundMembershipRepository(session_factory)
    api_key_repo = APIKeyRepository(session_factory)

    await _seed_platform(fund_repo, portfolio_repo, user_repo, membership_repo, api_key_repo)

    # --- OpenFGA ---
    fga_client = None
    if settings.fga_enabled:
        import app.shared.fga_resources  # noqa: F401 — triggers resource type registration
        from app.modules.platform.seed import build_seed_fga_tuples
        from app.shared.fga import initialize_fga

        fga_client = await initialize_fga(
            api_url=settings.fga_api_url,
            store_name=settings.fga_store_name,
        )
        fastapi_app.state.fga = fga_client
        tuples = build_seed_fga_tuples()
        await fga_client.write_tuples(tuples)
        logger.info("fga_tuples_seeded", count=len(tuples))

    # Auth service
    auth_service = AuthService(
        user_repo=user_repo,
        fund_repo=fund_repo,
        membership_repo=membership_repo,
        api_key_repo=api_key_repo,
        jwt_secret=settings.jwt_secret,
        jwt_algorithm=settings.jwt_algorithm,
        jwt_expiry_minutes=settings.jwt_expiry_minutes,
    )
    fastapi_app.state.auth_service = auth_service

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
    fastapi_app.state.engine = engine

    logger.info("app_started", env=settings.app_env, simulator=settings.simulator_enabled)

    yield

    # Shutdown
    if simulator is not None:
        simulator.stop()
    if simulator_task is not None:
        simulator_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await simulator_task

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

# Register routers
app.include_router(security_master_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")
app.include_router(positions_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


class TokenRequest(BaseModel):
    email: str
    fund_slug: str = "fund-alpha"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    actor_type: str
    fund_slug: str
    roles: list[str]


class AgentTokenRequest(BaseModel):
    agent_name: str
    fund_slug: str = "fund-alpha"
    roles: list[str] = ["viewer"]
    delegated_by_email: str | None = None


@app.post("/auth/token", response_model=TokenResponse)
async def create_token(request: TokenRequest) -> TokenResponse:
    """Issue a JWT for a registered user.

    In production this would be behind an IdP — here we validate
    the user exists and issue a token directly.
    """
    auth: AuthService = app.state.auth_service
    user = await auth._user_repo.get_by_email(request.email)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Unknown or inactive user")

    # Look up fund membership to get role
    fund = await auth._fund_repo.get_by_slug(request.fund_slug)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"Fund not found: {request.fund_slug}")

    membership = await auth._membership_repo.get_by_user_and_fund(user.id, fund.id)
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail=f"User has no access to fund {request.fund_slug}",
        )

    token = auth.create_token(
        actor_id=user.id,
        actor_type=ActorType.USER,
        fund_slug=request.fund_slug,
        roles=[membership.role],
    )

    return TokenResponse(
        access_token=token,
        actor_type="user",
        fund_slug=request.fund_slug,
        roles=[membership.role],
    )


@app.post("/auth/agent-token", response_model=TokenResponse)
async def create_agent_token(request: AgentTokenRequest) -> TokenResponse:
    """Issue a JWT for an LLM agent.

    If delegated_by_email is set, the token carries the delegating user's ID
    so downstream systems can audit who authorized the agent.
    """
    auth: AuthService = app.state.auth_service

    fund = await auth._fund_repo.get_by_slug(request.fund_slug)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"Fund not found: {request.fund_slug}")

    delegated_by: str | None = None
    if request.delegated_by_email:
        user = await auth._user_repo.get_by_email(request.delegated_by_email)
        if user is None:
            raise HTTPException(status_code=404, detail="Delegating user not found")
        delegated_by = user.id

    from uuid import uuid4

    agent_id = str(uuid4())
    token = auth.create_token(
        actor_id=agent_id,
        actor_type=ActorType.AGENT,
        fund_slug=request.fund_slug,
        roles=request.roles,
        delegated_by=delegated_by,
    )

    return TokenResponse(
        access_token=token,
        actor_type="agent",
        fund_slug=request.fund_slug,
        roles=request.roles,
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Readiness probe — checks PostgreSQL connectivity."""
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}
