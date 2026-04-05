"""FastAPI application entry point — wires modules, starts adapters, health check."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.security_master.service import SecurityMasterService

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.adapters.factory import (
    build_broker_adapter,
    build_market_data_adapter,
    build_reference_data_adapter,
)
from app.config import get_settings
from app.exception_handlers import register_exception_handlers
from app.middleware.auth import AuthMiddleware
from app.middleware.timeout import TimeoutMiddleware
from app.modules.alpha_engine.routes import router as alpha_router
from app.modules.attribution.routes import router as attribution_router
from app.modules.cash_management.routes import router as cash_router
from app.modules.compliance.routes import router as compliance_router
from app.modules.exposure.routes import router as exposure_router
from app.modules.market_data.routes import router as market_data_router
from app.modules.orders.routes import router as orders_router
from app.modules.platform.admin_routes import router as admin_router
from app.modules.platform.audit_repository import AuditLogRepository
from app.modules.platform.routes import router as platform_router
from app.modules.positions.routes import router as positions_router
from app.modules.realtime.routes import router as realtime_router
from app.modules.risk_engine.routes import router as risk_router
from app.modules.security_master.routes import router as security_master_router
from app.setup import (
    _run_migrations,
    setup_alpha_engine,
    setup_attribution,
    setup_cash_management,
    setup_compliance,
    setup_exposure,
    setup_fga,
    setup_market_data,
    setup_orders,
    setup_platform,
    setup_positions,
    setup_risk_engine,
    setup_security_master,
)
from app.shared.audit_bridge import AuditBridge
from app.shared.database import build_engine
from app.shared.fund_schema import ensure_all_fund_schemas
from app.shared.kafka import KafkaEventBus
from app.shared.logging import setup_logging
from app.shared.redis import create_redis_client
from app.shared.redis_bridge import RedisBridge
from app.shared.schema_registry import (
    fund_topics_for_slug,
    load_schemas,
    register_schemas,
    shared_topics,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Database
    engine, session_factory = build_engine()
    fastapi_app.state.session_factory = session_factory

    # Run migrations in thread pool (env.py uses sync psycopg2 to avoid
    # asyncio.run() conflicts with uvloop under uvicorn)
    await _run_migrations()

    # Configure structlog after migrations — Alembic's fileConfig creates
    # a root stderr handler that we reuse with structlog's formatter.
    setup_logging(settings.log_level)

    # Event bus — Kafka
    load_schemas()
    register_schemas(settings.kafka_schema_registry_url)

    kafka_bus = KafkaEventBus(
        settings.kafka_bootstrap_servers,
        consumer_group="minihedge",
        replication_factor=settings.kafka_replication_factor,
        num_partitions=settings.kafka_num_partitions,
    )

    # --- Build adapters from config ---
    broker_adapter = build_broker_adapter(settings)
    reference_adapter = build_reference_data_adapter(settings)
    market_data_adapter = build_market_data_adapter(settings, event_bus=kafka_bus)

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
    await setup_security_master(
        fastapi_app,
        session_factory,
        reference_adapter=reference_adapter,
    )

    # Create per-fund schemas and run positions migrations for each
    active_funds = await fund_repo.get_all_active()
    fund_slugs = [f.slug for f in active_funds]
    await ensure_all_fund_schemas(engine, fund_slugs)
    # Re-apply structlog config — Alembic's fileConfig() in per-fund
    # migrations resets the root logger, destroying structlog handlers.
    setup_logging(settings.log_level)
    logger.info("fund_schemas_ready", fund_count=len(fund_slugs))

    # Create Kafka topics — shared + per-fund + DLQ
    all_topics = shared_topics()
    for slug in fund_slugs:
        all_topics.extend(fund_topics_for_slug(slug))
    dlq_topics = [f"{t}.dlq" for t in all_topics]
    await kafka_bus.ensure_topics(all_topics + dlq_topics)

    sm_service: SecurityMasterService = fastapi_app.state.security_master_service
    setup_market_data(fastapi_app, session_factory, kafka_bus)
    await setup_positions(fastapi_app, session_factory, kafka_bus, fund_repo, sm_service)
    logger.info("phase_1_modules_ready")

    # Phase 2 modules — depend on positions + security_master being wired
    await setup_exposure(fastapi_app, session_factory, kafka_bus, fund_repo)
    await setup_compliance(fastapi_app, session_factory, fund_repo, kafka_bus)
    await setup_orders(fastapi_app, session_factory, kafka_bus, broker_adapter)
    logger.info("phase_2_modules_ready")

    # Phase 3 modules
    await setup_risk_engine(fastapi_app, session_factory, kafka_bus, fund_repo)
    await setup_cash_management(fastapi_app, session_factory, kafka_bus, fund_repo)
    await setup_attribution(fastapi_app, session_factory)
    await setup_alpha_engine(fastapi_app, session_factory)
    logger.info("phase_3_modules_ready")

    # Audit bridge — persists ALL fund-scoped events for compliance trail
    audit_repo = AuditLogRepository(session_factory)
    audit_bridge = AuditBridge(audit_repo)
    audit_bridge.wire(kafka_bus, fund_slugs)

    # Redis — bridge event bus to pub/sub for SSE streaming
    redis_client = None
    if settings.redis_enabled:
        redis_client = await create_redis_client(settings.redis_url)
        fastapi_app.state.redis = redis_client
        bridge = RedisBridge(redis_client)
        bridge.wire(kafka_bus, fund_slugs)

    # Start Kafka consumers (after all subscriptions are registered)
    logger.info("kafka_consumers_starting")
    await kafka_bus.start()
    logger.info("kafka_consumers_ready")

    # --- External market data adapter ---
    # Start the adapter's Kafka consumer that bridges vendor prices into
    # the internal event bus.
    logger.info("market_data_adapter_starting")
    instruments = await sm_service.get_all_active()
    tickers = [i.ticker for i in instruments]
    await market_data_adapter.start_streaming(tickers)
    logger.info("market_data_adapter_ready")

    # --- External broker fill consumer ---
    # When the broker is mock-exchange, start consuming execution reports
    # from the vendor's Kafka and forwarding fills to OrderService.
    if hasattr(broker_adapter, "start_fill_consumer"):
        logger.info("broker_fill_consumer_starting")
        order_service = fastapi_app.state.order_service
        order_service._fund_slugs = fund_slugs
        await broker_adapter.start_fill_consumer(order_service.process_execution_report)
        logger.info("broker_fill_consumer_ready")

    # Store references for health check
    fastapi_app.state.engine = engine
    fastapi_app.state.kafka_bus = kafka_bus

    # Store adapter config for visibility
    fastapi_app.state.market_data_source = settings.market_data_source
    fastapi_app.state.broker_adapter_type = settings.broker_adapter
    fastapi_app.state.reference_data_source = settings.reference_data_source

    logger.info(
        "app_started",
        env=settings.app_env,
        market_data_source=settings.market_data_source,
        broker_adapter=settings.broker_adapter,
        reference_data_source=settings.reference_data_source,
    )

    yield

    # Shutdown
    await market_data_adapter.stop_streaming()
    if hasattr(broker_adapter, "stop_fill_consumer"):
        await broker_adapter.stop_fill_consumer()

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

# Timeout middleware — outermost, prevents stuck workers (Starlette LIFO: added first = runs last)
app.add_middleware(TimeoutMiddleware)

# Auth middleware — looks up auth_service from app.state
app.add_middleware(AuthMiddleware)

# CORS — added after AuthMiddleware so it executes first (Starlette LIFO order),
# allowing preflight OPTIONS to succeed before auth runs.
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
app.include_router(exposure_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")
app.include_router(cash_router, prefix="/api/v1")
app.include_router(attribution_router, prefix="/api/v1")
app.include_router(alpha_router, prefix="/api/v1")


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
    if await app.state.kafka_bus.health_check():
        components["kafka"] = "healthy"
    else:
        components["kafka"] = "unhealthy: broker unreachable"

    all_healthy = all(v == "healthy" for v in components.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
        "adapters": {
            "market_data": app.state.market_data_source,
            "broker": app.state.broker_adapter_type,
            "reference_data": app.state.reference_data_source,
        },
    }
