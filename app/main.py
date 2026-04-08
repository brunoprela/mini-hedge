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
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.routing import Route

from app.adapters.factory import (
    build_alt_data_provider,
    build_broker_adapter,
    build_broker_registry,
    build_fund_admin_adapter,
    build_llm_adapter,
    build_market_data_adapter,
    build_reference_data_adapter,
)
from app.config import get_settings
from app.exception_handlers import register_exception_handlers
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import build_limiter, rate_limit_exceeded_handler
from app.middleware.timeout import TimeoutMiddleware
from app.modules.ai_analysis.routes import router as ai_analysis_router
from app.modules.alpha_engine.routes import router as alpha_router
from app.modules.alt_data.routes import router as alt_data_router
from app.modules.attribution.routes import router as attribution_router
from app.modules.backtesting.routes import router as backtesting_router
from app.modules.capital_accounts.routes import router as capital_router
from app.modules.cash_management.routes import router as cash_router
from app.modules.compliance.routes import router as compliance_router
from app.modules.corporate_actions.routes import router as corporate_actions_router
from app.modules.eod.recon_routes import router as recon_router
from app.modules.eod.routes import router as eod_router
from app.modules.exposure.routes import router as exposure_router
from app.modules.feature_store.routes import router as feature_store_router
from app.modules.fee_accounting.routes import router as fee_router
from app.modules.fund_structures.routes import router as fund_structures_router
from app.modules.fx_hedging.routes import router as fx_hedging_router
from app.modules.investor_operations.routes import router as investor_ops_router
from app.modules.market_data.routes import fx_router
from app.modules.market_data.routes import router as market_data_router
from app.modules.orders.allocation_routes import router as allocation_router
from app.modules.orders.broker_routes import router as broker_router
from app.modules.orders.routes import router as orders_router
from app.modules.orders.tca.routes import router as tca_router
from app.modules.platform.admin_routes import router as admin_router
from app.modules.platform.audit_repository import AuditLogRepository
from app.modules.platform.routes import router as platform_router
from app.modules.positions.routes import router as positions_router
from app.modules.quant_research.routes import router as quant_research_router
from app.modules.realtime.routes import router as realtime_router
from app.modules.regulatory.routes import router as regulatory_router
from app.modules.risk_engine.routes import router as risk_router
from app.modules.security_master.routes import router as security_master_router
from app.setup import (
    _run_migrations,
    setup_ai_analysis,
    setup_alpha_engine,
    setup_alt_data,
    setup_attribution,
    setup_backtesting,
    setup_capital_accounts,
    setup_cash_management,
    setup_compliance,
    setup_corporate_actions,
    setup_eod,
    setup_exposure,
    setup_feature_store,
    setup_fee_accounting,
    setup_fga,
    setup_fund_structures,
    setup_fx_hedging,
    setup_investor_operations,
    setup_market_data,
    setup_orders,
    setup_platform,
    setup_positions,
    setup_quant_research,
    setup_regulatory,
    setup_risk_engine,
    setup_security_master,
)
from app.shared.archival import MinioArchiver
from app.shared.archival_service import ArchivalService
from app.shared.audit_bridge import AuditBridge
from app.shared.cdc_audit_consumer import CdcAuditConsumer
from app.shared.cdc_transformer import CdcTransformer
from app.shared.database import TenantSessionFactory, build_engine
from app.shared.dlq_manager import DlqManager
from app.shared.fund_schema import ensure_all_fund_schemas
from app.shared.idempotency import IdempotencyMiddleware
from app.shared.immudb_bridge import ImmudbBridge
from app.shared.immudb_client import ImmudbClient
from app.shared.kafka import KafkaEventBus
from app.shared.logging import setup_logging
from app.shared.metrics import PrometheusMiddleware, metrics_route
from app.shared.opensearch_bridge import OpenSearchBridge
from app.shared.opensearch_client import OpenSearchClient
from app.shared.redis import create_redis_client
from app.shared.redis_bridge import RedisBridge
from app.shared.schema_registry import (
    fund_topics_for_slug,
    load_schemas,
    register_schemas,
    shared_topics,
)
from app.shared.telemetry import setup_telemetry
from app.shared.token_revocation import TokenRevocationService

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # OpenTelemetry — must be set up before other instrumented components
    setup_telemetry(fastapi_app)

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
    broker_registry = build_broker_registry(settings) if settings.broker_adapters else None
    reference_adapter = build_reference_data_adapter(settings)
    market_data_adapter = build_market_data_adapter(settings, event_bus=kafka_bus)
    fund_admin_adapter = build_fund_admin_adapter(settings)
    llm_adapter = build_llm_adapter(settings)
    alt_data_provider = build_alt_data_provider(settings)

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
    await setup_orders(
        fastapi_app,
        session_factory,
        kafka_bus,
        broker_adapter,
        broker_registry=broker_registry,
    )
    logger.info("phase_2_modules_ready")

    # Phase 3 modules
    await setup_risk_engine(fastapi_app, session_factory, kafka_bus, fund_repo)
    await setup_cash_management(fastapi_app, session_factory, kafka_bus, fund_repo)
    await setup_attribution(fastapi_app, session_factory)
    await setup_alpha_engine(fastapi_app, session_factory)
    await setup_fee_accounting(fastapi_app, session_factory)
    await setup_capital_accounts(fastapi_app, session_factory)
    await setup_corporate_actions(fastapi_app, session_factory, kafka_bus, settings)
    await setup_fx_hedging(fastapi_app, session_factory, kafka_bus)
    await setup_investor_operations(fastapi_app, session_factory, kafka_bus, settings)
    await setup_regulatory(fastapi_app, session_factory)
    await setup_fund_structures(fastapi_app, session_factory)
    await setup_backtesting(fastapi_app, session_factory)
    await setup_quant_research(fastapi_app, session_factory)
    await setup_ai_analysis(fastapi_app, session_factory, llm_adapter=llm_adapter)
    await setup_alt_data(fastapi_app, session_factory, alt_data_provider)
    await setup_feature_store(fastapi_app, session_factory, settings)
    await setup_eod(fastapi_app, session_factory, broker_adapter, fund_admin=fund_admin_adapter)
    logger.info("phase_3_modules_ready")

    # Audit bridge — persists ALL fund-scoped events for compliance trail
    audit_repo = AuditLogRepository(session_factory)
    audit_bridge = AuditBridge(audit_repo)
    audit_bridge.wire(kafka_bus, fund_slugs)

    # MinIO — cold-tier audit archival (S3-compatible Parquet export)
    if settings.minio_enabled:
        archiver = MinioArchiver(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
        )
        archiver.connect()
        archival_service = ArchivalService(
            archiver=archiver,
            audit_repo=audit_repo,
            fund_repo=fund_repo,
            session_factory=session_factory,
        )
        fastapi_app.state.archival_service = archival_service
        logger.info("minio_archival_ready", endpoint=settings.minio_endpoint)

    # immudb — tamper-proof audit witness (parallel Kafka consumer)
    immudb_client: ImmudbClient | None = None
    if settings.immudb_enabled:
        immudb_client = ImmudbClient(
            host=settings.immudb_host,
            port=settings.immudb_port,
            username=settings.immudb_username,
            password=settings.immudb_password,
            database=settings.immudb_database,
        )
        await immudb_client.connect()
        immudb_bridge = ImmudbBridge(immudb_client)
        immudb_bridge.wire(kafka_bus, fund_slugs)
        fastapi_app.state.immudb_client = immudb_client

    # OpenSearch — audit log search index (parallel Kafka consumer)
    opensearch_client: OpenSearchClient | None = None
    if settings.opensearch_enabled:
        opensearch_client = OpenSearchClient(
            host=settings.opensearch_host,
            port=settings.opensearch_port,
            username=settings.opensearch_username,
            password=settings.opensearch_password,
        )
        await opensearch_client.connect()
        opensearch_bridge = OpenSearchBridge(opensearch_client)
        opensearch_bridge.wire(kafka_bus, fund_slugs)
        fastapi_app.state.opensearch_client = opensearch_client

    # Redis — bridge event bus to pub/sub for SSE streaming
    redis_client = None
    if settings.redis_enabled:
        redis_client = await create_redis_client(settings.redis_url)
        fastapi_app.state.redis = redis_client
        fastapi_app.state.token_revocation = TokenRevocationService(redis_client)
        bridge = RedisBridge(redis_client)
        bridge.wire(kafka_bus, fund_slugs)

    # Start Kafka consumers (after all subscriptions are registered)
    logger.info("kafka_consumers_starting")
    await kafka_bus.start()
    logger.info("kafka_consumers_ready")

    # DLQ manager — admin API for inspecting/replaying dead letter queues
    fastapi_app.state.dlq_manager = DlqManager(settings.kafka_bootstrap_servers)

    # --- CDC transformer ---
    # Consumes Debezium CDC events from cdc.fund_* topics and re-publishes
    # as domain events on internal Kafka topics — replaces dual-writes.
    cdc_transformer = CdcTransformer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
    )
    await cdc_transformer.start()

    # --- CDC audit enrichment ---
    # Captures raw before/after row snapshots from CDC events for compliance.
    cdc_audit = CdcAuditConsumer(
        audit_repo=audit_repo,
        bootstrap_servers=settings.kafka_bootstrap_servers,
    )
    await cdc_audit.start()

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
    order_service = fastapi_app.state.order_service
    order_service._fund_slugs = fund_slugs

    if broker_registry is not None:
        # Multi-broker: start fill consumers for each broker adapter
        for bid in broker_registry.list_broker_ids():
            adapter = broker_registry.get(bid)
            start_fn = getattr(adapter, "start_fill_consumer", None)
            if start_fn is not None and not broker_registry.has_fill_consumer(bid):
                logger.info("broker_fill_consumer_starting", broker_id=bid)
                await start_fn(order_service.process_execution_report)
                broker_registry.mark_fill_consumer(bid)
                logger.info("broker_fill_consumer_ready", broker_id=bid)
    elif hasattr(broker_adapter, "start_fill_consumer"):
        logger.info("broker_fill_consumer_starting")
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
    if opensearch_client is not None:
        await opensearch_client.close()

    if immudb_client is not None:
        await immudb_client.close()

    await cdc_audit.stop()
    await cdc_transformer.stop()

    await market_data_adapter.stop_streaming()
    if broker_registry is not None:
        for bid in broker_registry.list_broker_ids():
            adapter = broker_registry.get(bid)
            stop_fn = getattr(adapter, "stop_fill_consumer", None)
            if stop_fn is not None and broker_registry.has_fill_consumer(bid):
                await stop_fn()
    elif hasattr(broker_adapter, "stop_fill_consumer"):
        await broker_adapter.stop_fill_consumer()

    await kafka_bus.stop()

    if redis_client is not None:
        await redis_client.aclose()

    if fga_client is not None:
        await fga_client.close()

    # Dispose read replica engine if configured
    if session_factory.has_read_replica:
        await session_factory._read_engine.dispose()  # type: ignore[union-attr]

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

# Idempotency middleware — added after auth (Starlette LIFO: runs before auth),
# so duplicate mutations short-circuit before auth/handler work.
app.add_middleware(IdempotencyMiddleware)

# CORS — added after AuthMiddleware so it executes first (Starlette LIFO order),
# allowing preflight OPTIONS to succeed before auth runs.
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Fund-Slug", "X-API-Key", "Idempotency-Key"],
)

# Prometheus middleware — outermost layer, wraps everything including auth/timeout
# (Starlette LIFO: added last = runs first)
app.add_middleware(PrometheusMiddleware)

# Rate limiting — Redis-backed, per-API-key/per-IP
_redis_url = _settings.redis_url if _settings.redis_enabled else None
_limiter = build_limiter(_redis_url)
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

register_exception_handlers(app)

# Register routers
app.include_router(platform_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(security_master_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")
app.include_router(fx_router, prefix="/api/v1")
app.include_router(positions_router, prefix="/api/v1")
app.include_router(realtime_router, prefix="/api/v1")
app.include_router(exposure_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")
app.include_router(cash_router, prefix="/api/v1")
app.include_router(attribution_router, prefix="/api/v1")
app.include_router(alpha_router, prefix="/api/v1")
app.include_router(eod_router, prefix="/api/v1")
app.include_router(recon_router, prefix="/api/v1")
app.include_router(fee_router, prefix="/api/v1")
app.include_router(capital_router, prefix="/api/v1")
app.include_router(corporate_actions_router, prefix="/api/v1")
app.include_router(allocation_router, prefix="/api/v1")
app.include_router(broker_router, prefix="/api/v1")
app.include_router(tca_router, prefix="/api/v1")
app.include_router(fx_hedging_router, prefix="/api/v1")
app.include_router(investor_ops_router, prefix="/api/v1")
app.include_router(regulatory_router, prefix="/api/v1")
app.include_router(fund_structures_router, prefix="/api/v1")
app.include_router(backtesting_router, prefix="/api/v1")
app.include_router(quant_research_router, prefix="/api/v1")
app.include_router(ai_analysis_router, prefix="/api/v1")
app.include_router(alt_data_router, prefix="/api/v1")
app.include_router(feature_store_router, prefix="/api/v1")

# Prometheus metrics endpoint — plain Starlette route (bypasses auth via PUBLIC_PATHS)
app.routes.append(Route("/metrics", metrics_route))


@app.get("/health")
async def health_check() -> dict[str, object]:
    """Readiness probe — checks PostgreSQL, Redis, and Kafka connectivity."""
    components: dict[str, str] = {}

    # PostgreSQL (primary via PgBouncer)
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components["postgres"] = "healthy"
    except Exception as e:
        components["postgres"] = f"unhealthy: {e}"

    # PostgreSQL read replica
    sf: TenantSessionFactory = app.state.session_factory
    if sf.has_read_replica:
        try:
            async with sf._read_engine.connect() as conn:  # type: ignore[union-attr]
                await conn.execute(text("SELECT 1"))
            components["postgres_replica"] = "healthy"
        except Exception as e:
            components["postgres_replica"] = f"unhealthy: {e}"

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
