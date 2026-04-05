"""Integration test fixtures — real PostgreSQL via testcontainers.

Sets up a multi-fund environment with three funds, each with their own
per-fund PostgreSQL schema, portfolios, and API keys.  Shared data
(security_master, market_data) is migrated once.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
import pytest_asyncio
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.cash_management.repository import (
    CashBalanceRepository,
    CashJournalRepository,
    CashProjectionRepository,
    ScheduledFlowRepository,
    SettlementRepository,
)
from app.modules.cash_management.service import CashManagementService
from app.modules.compliance.post_trade import PostTradeMonitor
from app.modules.compliance.pre_trade import PreTradeGate
from app.modules.compliance.repository import RuleRepository, ViolationRepository
from app.modules.compliance.service import ComplianceService
from app.modules.exposure.repository import ExposureRepository
from app.modules.exposure.service import ExposureService
from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.repository import PriceRepository
from app.modules.market_data.service import MarketDataService
from app.modules.orders.compliance_gateway import ComplianceGateway
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService
from app.modules.platform.audit_repository import AuditLogRepository
from app.modules.platform.models import Base as PlatformBase
from app.modules.platform.seed import (
    FUND_ALPHA_ID,
    FUND_BETA_ID,
    FUND_GAMMA_ID,
    PORTFOLIO_ALPHA_EQUITY_LS_ID,
    PORTFOLIO_BETA_STAT_ARB_ID,
    PORTFOLIO_GAMMA_EVENT_DRIVEN_ID,
    build_seed_api_keys,
    build_seed_funds,
    build_seed_operators,
    build_seed_portfolios,
    build_seed_users,
)
from app.modules.positions.event_store import EventStoreRepository
from app.modules.positions.mtm_handler import MarkToMarketHandler
from app.modules.positions.position_projector import PositionProjector
from app.modules.positions.position_repository import CurrentPositionRepository
from app.modules.positions.service import PositionService
from app.modules.positions.trade_handler import TradeHandler
from app.modules.risk_engine.repository import RiskRepository
from app.modules.risk_engine.service import RiskService
from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.seed import build_seed_records
from app.modules.security_master.service import SecurityMasterService
from app.shared.database import TenantSessionFactory
from app.shared.events import BaseEvent, EventHandler, InProcessEventBus
from app.shared.fund_schema import fund_schema_name
from app.shared.request_context import ActorType, RequestContext, set_request_context
from app.shared.schema_registry import fund_topic, shared_topic
from tests.helpers import EventCapture, StubBroker

if TYPE_CHECKING:
    from app.shared.types import AssetClass

# Shared migrations — run once against the default public/named schema.
MIGRATION_CONTEXTS = ["platform", "security_master", "market_data"]

# Per-fund migrations — run once per fund against fund_{slug} schema.
PER_FUND_MIGRATION_CONTEXTS = [
    "positions",
    "orders",
    "compliance",
    "exposure",
    "cash_management",
    "risk_engine",
    "alpha_engine",
    "attribution",
]

# All three test funds — each gets a per-fund schema
TEST_FUND_SLUGS = ["alpha", "beta", "gamma"]


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Start a PostgreSQL container, run migrations, seed platform data."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url()
        sync_url = url.replace("+asyncpg", "")

        # 1. Run shared Alembic migrations for each bounded context.
        for ctx in MIGRATION_CONTEXTS:
            cfg = AlembicConfig("alembic.ini", ini_section=ctx)
            cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
            cfg.set_section_option(ctx, "sqlalchemy.url", url)
            alembic_command.upgrade(cfg, "head")

        # 2. Seed platform data (funds, portfolios, users, operators, API keys)
        engine = create_engine(sync_url)
        _seed_platform_sync(engine)

        # 3. Create per-fund schemas and run all per-fund migrations
        for slug in TEST_FUND_SLUGS:
            schema = fund_schema_name(slug)
            with engine.connect() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
                conn.commit()

            for ctx in PER_FUND_MIGRATION_CONTEXTS:
                cfg = AlembicConfig("alembic.ini", ini_section=ctx)
                cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
                cfg.set_section_option(ctx, "sqlalchemy.url", url)
                cfg.attributes["target_schema"] = schema
                alembic_command.upgrade(cfg, "head")

        engine.dispose()

        yield url


def _seed_platform_sync(engine) -> None:  # type: ignore[no-untyped-def]
    """Insert seed data into the platform schema using sync engine."""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        # Funds
        for fund in build_seed_funds():
            session.execute(
                PlatformBase.metadata.tables["platform.funds"]
                .insert()
                .values(
                    id=fund.id,
                    slug=fund.slug,
                    name=fund.name,
                    status=fund.status,
                    base_currency=fund.base_currency,
                )
            )

        # Portfolios
        for p in build_seed_portfolios():
            session.execute(
                PlatformBase.metadata.tables["platform.portfolios"]
                .insert()
                .values(
                    id=p.id,
                    fund_id=p.fund_id,
                    slug=p.slug,
                    name=p.name,
                    strategy=p.strategy,
                )
            )

        # Users
        for u in build_seed_users():
            session.execute(
                PlatformBase.metadata.tables["platform.users"]
                .insert()
                .values(
                    id=u.id,
                    email=u.email,
                    name=u.name,
                    is_active=u.is_active,
                )
            )

        # Operators
        for op in build_seed_operators():
            session.execute(
                PlatformBase.metadata.tables["platform.operators"]
                .insert()
                .values(
                    id=op.id,
                    email=op.email,
                    name=op.name,
                    is_active=op.is_active,
                )
            )

        # API keys
        for k in build_seed_api_keys():
            session.execute(
                PlatformBase.metadata.tables["platform.api_keys"]
                .insert()
                .values(
                    id=k.id,
                    key_hash=k.key_hash,
                    name=k.name,
                    actor_type=k.actor_type,
                    fund_id=k.fund_id,
                    roles=k.roles,
                )
            )

        session.commit()


@pytest_asyncio.fixture
async def session_factory(postgres_url: str) -> TenantSessionFactory:
    """Create engine + tenant session factory against the migrated test database."""
    engine = create_async_engine(postgres_url, echo=False)
    yield TenantSessionFactory(engine)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Request contexts — one per fund, autouse default is fund-alpha
# ---------------------------------------------------------------------------


def _make_context(
    fund_slug: str,
    fund_id: str,
    actor_id: str = "test-user",
    roles: frozenset[str] | None = None,
) -> RequestContext:
    return RequestContext(
        actor_id=actor_id,
        actor_type=ActorType.USER,
        fund_slug=fund_slug,
        fund_id=fund_id,
        roles=roles or frozenset({"admin"}),
        permissions=frozenset(),
    )


@pytest.fixture(autouse=True)
def request_context() -> RequestContext:
    """Default request context — fund-alpha, admin role."""
    ctx = _make_context("alpha", FUND_ALPHA_ID)
    set_request_context(ctx)
    return ctx


@pytest.fixture
def alpha_context() -> RequestContext:
    """Explicit fund-alpha context."""
    ctx = _make_context("alpha", FUND_ALPHA_ID)
    set_request_context(ctx)
    return ctx


@pytest.fixture
def beta_context() -> RequestContext:
    """Fund-beta context (Bridgewater Systematic)."""
    ctx = _make_context("beta", FUND_BETA_ID, actor_id="beta-pm")
    set_request_context(ctx)
    return ctx


@pytest.fixture
def gamma_context() -> RequestContext:
    """Fund-gamma context (Citrine Event-Driven)."""
    ctx = _make_context("gamma", FUND_GAMMA_ID, actor_id="gamma-pm")
    set_request_context(ctx)
    return ctx


# ---------------------------------------------------------------------------
# Convenience: well-known portfolio IDs for tests
# ---------------------------------------------------------------------------

ALPHA_PORTFOLIO_ID = PORTFOLIO_ALPHA_EQUITY_LS_ID
BETA_PORTFOLIO_ID = PORTFOLIO_BETA_STAT_ARB_ID
GAMMA_PORTFOLIO_ID = PORTFOLIO_GAMMA_EVENT_DRIVEN_ID


# ---------------------------------------------------------------------------
# WiredSystem — fully wired system for cascade integration tests
# ---------------------------------------------------------------------------


@dataclass
class WiredSystem:
    """All services wired together with InProcessEventBus + real DB repos.

    Mirrors ``app/setup.py`` wiring but headless (no FastAPI app).
    """

    event_bus: InProcessEventBus
    capture: EventCapture
    session_factory: TenantSessionFactory
    # Services
    order_service: OrderService
    position_service: PositionService
    trade_handler: TradeHandler
    mtm_handler: MarkToMarketHandler
    market_data_service: MarketDataService
    security_master: SecurityMasterService
    exposure_service: ExposureService
    risk_service: RiskService
    compliance_service: ComplianceService
    post_trade_monitor: PostTradeMonitor
    cash_service: CashManagementService
    # Broker
    broker: StubBroker


@pytest_asyncio.fixture
async def wired_system(session_factory: TenantSessionFactory) -> WiredSystem:
    """Build the full service graph wired via InProcessEventBus + real repos."""
    bus = InProcessEventBus()
    capture = EventCapture()
    broker = StubBroker()

    # --- Repositories --------------------------------------------------------
    instrument_repo = InstrumentRepository(session_factory)
    price_repo = PriceRepository(session_factory)
    event_store_repo = EventStoreRepository(session_factory)
    position_repo = CurrentPositionRepository(session_factory)
    order_repo = OrderRepository(session_factory)
    exposure_repo = ExposureRepository(session_factory)
    risk_repo = RiskRepository(session_factory)
    rule_repo = RuleRepository(session_factory)
    violation_repo = ViolationRepository(session_factory)
    cash_balance_repo = CashBalanceRepository(session_factory)
    audit_repo = AuditLogRepository(session_factory)

    # --- Core services (no event dependencies) --------------------------------
    security_master = SecurityMasterService(repository=instrument_repo)

    # Seed instruments if not already present
    existing = await instrument_repo.get_all_active()
    if not existing:
        instruments, extensions = build_seed_records()
        await instrument_repo.insert_batch(instruments, extensions)

    market_data_service = MarketDataService(repository=price_repo)

    # --- Positions module -----------------------------------------------------
    projector = PositionProjector(position_repo)
    trade_handler = TradeHandler(
        session_factory=session_factory,
        event_store=event_store_repo,
        projector=projector,
        event_bus=bus,
    )
    position_service = PositionService(
        position_repo=position_repo,
        trade_handler=trade_handler,
    )

    # --- Compliance module ----------------------------------------------------
    pre_trade_gate = PreTradeGate(
        rule_repo=rule_repo,
        position_service=position_service,
        security_master=security_master,
        cash_balance_repo=cash_balance_repo,
    )
    compliance_service = ComplianceService(
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        pre_trade_gate=pre_trade_gate,
        audit_repo=audit_repo,
        position_service=position_service,
        security_master=security_master,
    )

    post_trade_monitor = PostTradeMonitor(
        session_factory=session_factory,
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        position_repo=position_repo,
        security_master=security_master,
        event_bus=bus,
        cash_balance_repo=cash_balance_repo,
    )

    # --- Exposure + Risk modules ----------------------------------------------
    exposure_service = ExposureService(
        exposure_repo=exposure_repo,
        position_service=position_service,
        security_master_service=security_master,
        event_bus=bus,
    )

    risk_service = RiskService(
        risk_repo=risk_repo,
        position_service=position_service,
        market_data_service=market_data_service,
        security_master_service=security_master,
        event_bus=bus,
    )

    # --- Cash management ------------------------------------------------------
    cash_service = CashManagementService(
        session_factory=session_factory,
        balance_repo=cash_balance_repo,
        journal_repo=CashJournalRepository(session_factory),
        settlement_repo=SettlementRepository(session_factory),
        scheduled_flow_repo=ScheduledFlowRepository(session_factory),
        projection_repo=CashProjectionRepository(session_factory),
        security_master_service=security_master,
        event_bus=bus,
    )

    # --- Orders module --------------------------------------------------------
    compliance_gateway = ComplianceGateway(pre_trade_gate=pre_trade_gate)
    order_service = OrderService(
        session_factory=session_factory,
        order_repo=order_repo,
        compliance_gateway=compliance_gateway,
        broker=broker,
        event_bus=bus,
        audit_repo=audit_repo,
    )

    # --- MTM handler ----------------------------------------------------------
    async def get_fund_slugs() -> list[str]:
        return TEST_FUND_SLUGS

    async def get_asset_class(instrument_id: str) -> AssetClass | None:
        try:
            instrument = await security_master.get_by_ticker(instrument_id)
        except Exception:
            return None
        return instrument.asset_class

    mtm_handler = MarkToMarketHandler(
        session_factory=session_factory,
        event_bus=bus,
        get_fund_slugs=get_fund_slugs,
        get_asset_class=get_asset_class,
    )

    # --- Wire event subscriptions (mirrors setup.py) --------------------------

    # Market data: store price snapshots
    def _make_price_handler(mds: MarketDataService) -> EventHandler:
        async def on_price(event: BaseEvent) -> None:
            data = event.data
            required = ("instrument_id", "bid", "ask", "mid", "source")
            if not all(k in data for k in required):
                return
            raw_volume = data.get("volume")
            snapshot = PriceSnapshot(
                instrument_id=data["instrument_id"],
                bid=Decimal(data["bid"]),
                ask=Decimal(data["ask"]),
                mid=Decimal(data["mid"]),
                volume=Decimal(raw_volume) if raw_volume is not None else None,
                timestamp=event.timestamp,
                source=data["source"],
            )
            mds.update_latest(snapshot)
            await mds.store_price(snapshot)

        return on_price

    bus.subscribe(shared_topic("prices.normalized"), _make_price_handler(market_data_service))
    bus.subscribe(shared_topic("prices.normalized"), mtm_handler.handle_price_update)

    for slug in TEST_FUND_SLUGS:
        # trades.executed → TradeHandler + CashManagement
        bus.subscribe(fund_topic(slug, "trades.executed"), trade_handler.handle_trade_event)
        bus.subscribe(fund_topic(slug, "trades.executed"), cash_service.handle_trade_executed)

        # positions.changed → Exposure, Risk, Compliance (PostTradeMonitor)
        # Handlers wrapped with try/except to match production behavior (setup.py)
        def _make_exposure_handler(s: str) -> EventHandler:
            async def on_pos(event: BaseEvent) -> None:
                pid = event.data.get("portfolio_id")
                if not pid:
                    return
                with contextlib.suppress(Exception):
                    await exposure_service.take_snapshot(UUID(pid), fund_slug=s)

            return on_pos

        def _make_risk_handler(s: str) -> EventHandler:
            async def on_pos(event: BaseEvent) -> None:
                pid = event.data.get("portfolio_id")
                if not pid:
                    return
                with contextlib.suppress(Exception):
                    await risk_service.take_snapshot(UUID(pid), fund_slug=s)

            return on_pos

        bus.subscribe(fund_topic(slug, "positions.changed"), _make_exposure_handler(slug))
        bus.subscribe(fund_topic(slug, "positions.changed"), _make_risk_handler(slug))
        bus.subscribe(
            fund_topic(slug, "positions.changed"),
            post_trade_monitor.handle_position_changed,
        )

        # pnl.updated → PostTradeMonitor (passive breach detection)
        bus.subscribe(fund_topic(slug, "pnl.updated"), post_trade_monitor.handle_mtm_update)

    # --- Wire EventCapture to all topics for assertion ------------------------
    all_topics: list[str] = [shared_topic("prices.normalized")]
    for slug in TEST_FUND_SLUGS:
        all_topics.extend(
            [
                fund_topic(slug, "trades.executed"),
                fund_topic(slug, "positions.changed"),
                fund_topic(slug, "pnl.updated"),
                fund_topic(slug, "compliance.violations"),
                fund_topic(slug, "cash.settlement.created"),
                fund_topic(slug, "cash.settlement.settled"),
                fund_topic(slug, "exposure.snapshot"),
                fund_topic(slug, "risk.snapshot"),
            ]
        )
    capture.wire_to_bus(bus, all_topics)

    return WiredSystem(
        event_bus=bus,
        capture=capture,
        session_factory=session_factory,
        order_service=order_service,
        position_service=position_service,
        trade_handler=trade_handler,
        mtm_handler=mtm_handler,
        market_data_service=market_data_service,
        security_master=security_master,
        exposure_service=exposure_service,
        risk_service=risk_service,
        compliance_service=compliance_service,
        post_trade_monitor=post_trade_monitor,
        cash_service=cash_service,
        broker=broker,
    )
