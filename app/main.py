"""FastAPI application entry point — wires modules, starts simulator, health check."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from sqlalchemy import text

if TYPE_CHECKING:
    from app.modules.security_master.service import SecurityMasterService
    from app.shared.events import EventBus

from app.config import get_settings
from app.exception_handlers import register_exception_handlers
from app.middleware.auth import AuthMiddleware
from app.modules.market_data.routes import router as market_data_router
from app.modules.market_data.simulator import MarketDataSimulator
from app.modules.platform.admin_routes import router as admin_router
from app.modules.platform.audit_repository import AuditLogRepository
from app.modules.platform.routes import router as platform_router
from app.modules.positions.routes import router as positions_router
from app.modules.realtime.routes import router as realtime_router
from app.modules.security_master.routes import router as security_master_router
from app.setup import (
    _run_migrations,
    setup_fga,
    setup_market_data,
    setup_platform,
    setup_positions,
    setup_security_master,
)
from app.shared.database import build_engine
from app.shared.fund_schema import ensure_all_fund_schemas
from app.shared.logging import setup_logging
from app.shared.schema_registry import fund_topic, fund_topics_for_slug, shared_topics

logger = structlog.get_logger()


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
    # FGA must init before platform (AuthService depends on FGAClient)
    fga_client = await setup_fga(fastapi_app, settings)
    auth_service, fund_repo = await setup_platform(
        fastapi_app,
        session_factory,
        settings,
        fga_client=fga_client,
        engine=engine,
        event_bus=kafka_bus,
    )
    await setup_security_master(fastapi_app, session_factory)

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

    setup_market_data(fastapi_app, session_factory, event_bus)
    sm_service: SecurityMasterService = fastapi_app.state.security_master_service
    setup_positions(fastapi_app, session_factory, event_bus, fund_repo, sm_service)

    # Audit log consumer — persists trade events for compliance trail
    audit_repo = AuditLogRepository(session_factory)
    for slug in fund_slugs:
        event_bus.subscribe(
            fund_topic(slug, "trades.executed"),
            audit_repo.insert,
        )

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

# CORS — added after AuthMiddleware so it executes first (Starlette LIFO order),
# allowing preflight OPTIONS to succeed before auth runs.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Fund-Slug", "X-API-Key"],
)

register_exception_handlers(app)

# Register routers
app.include_router(platform_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
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
    if app.state.kafka_bus.health_check():
        components["kafka"] = "healthy"
    else:
        components["kafka"] = "unhealthy: flush failed"

    all_healthy = all(v == "healthy" for v in components.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
    }
