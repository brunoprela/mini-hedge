"""FastAPI application entry point — wires modules, starts adapters, health check."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.rate_limit import build_limiter, rate_limit_exceeded_handler
from app.middleware.timeout import TimeoutMiddleware
from app.modules.platform.audit_repository import AuditLogRepository
from app.routes import register_all
from app.setup import _run_migrations, setup_all
from app.shared.audit.archival import MinioArchiver
from app.shared.audit.archival_service import ArchivalService
from app.shared.audit.bridge import AuditBridge
from app.shared.audit.cdc_consumer import CdcAuditConsumer
from app.shared.audit.cdc_transformer import CdcTransformer
from app.shared.auth.token_revocation import TokenRevocationService
from app.shared.database import TenantSessionFactory, build_engine
from app.shared.dlq_manager import DlqManager
from app.shared.kafka import KafkaEventBus
from app.shared.observability.logging import setup_logging
from app.shared.observability.metrics import PrometheusMiddleware, metrics_route
from app.shared.observability.telemetry import setup_telemetry
from app.shared.schema_registry import load_schemas, register_schemas
from app.shared.stores.immudb_bridge import ImmudbBridge
from app.shared.stores.immudb_client import ImmudbClient
from app.shared.stores.opensearch_bridge import OpenSearchBridge
from app.shared.stores.opensearch_client import OpenSearchClient
from app.shared.stores.redis import create_redis_client
from app.shared.stores.redis_bridge import RedisBridge

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

    # --- Module setup (delegated to per-module wiring.py files) ---
    fund_slugs = await setup_all(
        fastapi_app,
        session_factory,
        engine=engine,
        event_bus=kafka_bus,
        settings=settings,
        broker=broker_adapter,
        broker_registry=broker_registry,
        reference_adapter=reference_adapter,
        llm_adapter=llm_adapter,
        alt_data_provider=alt_data_provider,
        fund_admin=fund_admin_adapter,
    )

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
            fund_repo=fastapi_app.state.fund_repo,
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
    sm_service = fastapi_app.state.security_master_service
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

    fga_client = getattr(fastapi_app.state, "fga", None)
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
register_all(app)

# Prometheus metrics endpoint — plain Starlette route (bypasses auth via PUBLIC_PATHS)
app.routes.append(Route("/metrics", metrics_route))


@app.get("/healthz")
async def liveness() -> dict[str, str]:
    """Liveness probe — is the process alive? No dependency checks."""
    return {"status": "alive"}


@app.get("/readyz")
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
