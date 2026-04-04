"""Module wiring and lifespan helpers — migrations, seeding, per-module setup."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.adapters import BrokerAdapter, ExternalInstrument, ReferenceDataAdapter
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus
    from app.shared.types import AssetClass

from app.modules.market_data.interface import PriceSnapshot
from app.modules.market_data.repository import PriceRepository
from app.modules.market_data.service import MarketDataService
from app.modules.platform.admin_service import AdminService
from app.modules.platform.api_key_repository import APIKeyRepository
from app.modules.platform.audit_repository import AuditLogRepository
from app.modules.platform.auth_service import AuthService
from app.modules.platform.fund_repository import FundRepository
from app.modules.platform.operator_repository import OperatorRepository
from app.modules.platform.portfolio_repository import PortfolioRepository
from app.modules.platform.seed import (
    DEV_API_KEY,
    build_seed_api_keys,
    build_seed_funds,
    build_seed_portfolios,
    build_seed_users,
)
from app.modules.platform.user_repository import UserRepository
from app.modules.positions.event_store import EventStoreRepository
from app.modules.positions.mtm_handler import MarkToMarketHandler
from app.modules.positions.position_projector import PositionProjector
from app.modules.positions.position_repository import CurrentPositionRepository
from app.modules.positions.service import PositionService
from app.modules.positions.trade_handler import TradeHandler
from app.modules.security_master.models import EquityExtensionRecord, InstrumentRecord
from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.seed import build_seed_records
from app.modules.security_master.service import SecurityMasterService
from app.shared.schema_registry import fund_topic, shared_topic

logger = structlog.get_logger()

# Bounded contexts whose Alembic migrations run on startup.
# Positions are NOT here — each fund gets its own schema, created
# by ensure_all_fund_schemas() after platform seeding discovers active funds.
MIGRATION_CONTEXTS = ["platform", "security_master", "market_data"]


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


async def _seed_instruments(
    repo: InstrumentRepository,
    *,
    reference_adapter: ReferenceDataAdapter | None = None,
) -> None:
    existing = await repo.get_all_active()
    if existing:
        return

    if reference_adapter is not None:
        externals = await reference_adapter.get_all_instruments()
        instruments, extensions = _convert_external_instruments(externals)
        logger.info("instruments_fetched_from_adapter", count=len(instruments))
    else:
        instruments, extensions = build_seed_records()

    await repo.insert_batch(instruments, extensions)
    logger.info("instruments_seeded", count=len(instruments), extensions=len(extensions))


def _convert_external_instruments(
    externals: list[ExternalInstrument],
) -> tuple[list[InstrumentRecord], list[EquityExtensionRecord]]:
    """Convert adapter ExternalInstrument objects to ORM records."""
    from uuid import uuid4

    instruments: list[InstrumentRecord] = []
    extensions: list[EquityExtensionRecord] = []
    for ext in externals:
        instrument_id = str(uuid4())
        instruments.append(
            InstrumentRecord(
                id=instrument_id,
                name=ext.name,
                ticker=ext.ticker,
                asset_class=ext.asset_class,
                currency=ext.currency,
                exchange=ext.exchange,
                country=ext.country,
                sector=ext.sector,
                industry=ext.industry,
                annual_drift=ext.annual_drift,
                annual_volatility=ext.annual_volatility,
                spread_bps=ext.spread_bps,
                is_active=ext.is_active,
            )
        )
    return instruments, extensions


async def _seed_platform(
    fund_repo: FundRepository,
    portfolio_repo: PortfolioRepository,
    user_repo: UserRepository,
    operator_repo: OperatorRepository,
    api_key_repo: APIKeyRepository,
) -> None:
    """Seed funds, portfolios, users, operators, and API keys."""
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
        api_keys = build_seed_api_keys()
        for api_key in api_keys:
            await api_key_repo.insert(api_key)
        logger.info(
            "auth_seeded",
            users=len(users),
            api_key=DEV_API_KEY,
        )

    # Seed operators
    from app.modules.platform.seed import build_seed_operators

    existing_operators = await operator_repo.get_all_active()
    if not existing_operators:
        operators = build_seed_operators()
        for op in operators:
            await operator_repo.insert(op)
        logger.info("operators_seeded", count=len(operators))


# ---------------------------------------------------------------------------
# Per-module setup helpers (called from lifespan)
# ---------------------------------------------------------------------------


async def setup_platform(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    settings: object,
    fga_client: object | None = None,
    engine: object | None = None,
    event_bus: object | None = None,
) -> tuple[AuthService, FundRepository]:
    """Wire platform module: repos, seeding, auth service."""
    fund_repo = FundRepository(session_factory)
    portfolio_repo = PortfolioRepository(session_factory)
    user_repo = UserRepository(session_factory)
    operator_repo = OperatorRepository(session_factory)
    api_key_repo = APIKeyRepository(session_factory)

    await _seed_platform(fund_repo, portfolio_repo, user_repo, operator_repo, api_key_repo)

    auth_service = AuthService(
        user_repo=user_repo,
        fund_repo=fund_repo,
        operator_repo=operator_repo,
        api_key_repo=api_key_repo,
        fga_client=fga_client,  # type: ignore[arg-type]
        jwt_secret=settings.jwt_secret,  # type: ignore[attr-defined]
        jwt_algorithm=settings.jwt_algorithm,  # type: ignore[attr-defined]
        jwt_expiry_minutes=settings.jwt_expiry_minutes,  # type: ignore[attr-defined]
        keycloak_url=settings.keycloak_url,  # type: ignore[attr-defined]
        keycloak_browser_url=settings.keycloak_browser_url,  # type: ignore[attr-defined]
        keycloak_realm=settings.keycloak_realm,  # type: ignore[attr-defined]
        keycloak_client_id=settings.keycloak_client_id,  # type: ignore[attr-defined]
        keycloak_ops_realm=settings.keycloak_ops_realm,  # type: ignore[attr-defined]
        keycloak_ops_client_id=settings.keycloak_ops_client_id,  # type: ignore[attr-defined]
    )
    fastapi_app.state.auth_service = auth_service
    fastapi_app.state.portfolio_repo = portfolio_repo
    fastapi_app.state.operator_repo = operator_repo

    audit_repo = AuditLogRepository(session_factory)
    fastapi_app.state.audit_repo = audit_repo

    # Admin service (only if FGA is available)
    if fga_client is not None:
        admin_service = AdminService(
            user_repo=user_repo,
            operator_repo=operator_repo,
            fund_repo=fund_repo,
            fga_client=fga_client,  # type: ignore[arg-type]
            audit_repo=audit_repo,
            engine=engine,  # type: ignore[arg-type]
            event_bus=event_bus,  # type: ignore[arg-type]
            auth_service=auth_service,
        )
        fastapi_app.state.admin_service = admin_service

    return auth_service, fund_repo


async def setup_fga(fastapi_app: FastAPI, settings: object) -> object | None:
    """Initialize OpenFGA if enabled. Returns the FGA client or None."""
    if not settings.fga_enabled:  # type: ignore[attr-defined]
        return None

    import app.shared.fga_resources  # noqa: F401 — triggers resource type registration
    from app.modules.platform.seed import build_seed_fga_tuples
    from app.shared.fga_startup import initialize_fga

    fga_client = await initialize_fga(
        api_url=settings.fga_api_url,  # type: ignore[attr-defined]
        store_name=settings.fga_store_name,  # type: ignore[attr-defined]
    )
    fastapi_app.state.fga = fga_client
    tuples = build_seed_fga_tuples()
    await fga_client.write_tuples(tuples)
    logger.info("fga_tuples_seeded", count=len(tuples))
    return fga_client


async def setup_security_master(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    *,
    reference_adapter: ReferenceDataAdapter | None = None,
) -> None:
    """Wire security master module: repo, service, seeding."""
    instrument_repo = InstrumentRepository(session_factory)
    fastapi_app.state.security_master_service = SecurityMasterService(instrument_repo)
    await _seed_instruments(instrument_repo, reference_adapter=reference_adapter)


def setup_market_data(
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


def setup_positions(
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


async def setup_exposure(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    event_bus: EventBus | None = None,
    fund_repo: FundRepository | None = None,
) -> None:
    """Wire exposure module: repo, service, event subscriptions."""
    from app.modules.exposure.repository import ExposureRepository
    from app.modules.exposure.service import ExposureService

    exposure_repo = ExposureRepository(session_factory)
    position_service = fastapi_app.state.position_service
    sm_service = fastapi_app.state.security_master_service
    exposure_service = ExposureService(
        exposure_repo=exposure_repo,
        position_service=position_service,
        security_master_service=sm_service,
        event_bus=event_bus,
    )
    fastapi_app.state.exposure_service = exposure_service

    # Subscribe: recalculate exposure when positions change
    if event_bus is not None and fund_repo is not None:
        active_funds = await fund_repo.get_all_active()
        for fund in active_funds:

            def _make_handler(slug: str):  # type: ignore[no-untyped-def]
                async def on_position_changed(event: BaseEvent) -> None:
                    pid_str = event.data.get("portfolio_id")
                    if not pid_str:
                        return
                    from uuid import UUID

                    try:
                        await exposure_service.take_snapshot(
                            UUID(pid_str),
                            fund_slug=slug,
                        )
                    except Exception:
                        logger.exception(
                            "exposure_reactive_snapshot_failed",
                            portfolio_id=pid_str,
                        )

                return on_position_changed

            event_bus.subscribe(
                fund_topic(fund.slug, "positions.changed"),
                _make_handler(fund.slug),
            )
        logger.info(
            "exposure_subscribed_to_positions",
            fund_count=len(active_funds),
        )


async def setup_compliance(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    fund_repo: FundRepository,
    event_bus: EventBus,
) -> None:
    """Wire compliance module: repos, pre-trade gate, post-trade monitor, service, seeding."""
    from app.modules.compliance.post_trade import PostTradeMonitor
    from app.modules.compliance.pre_trade import PreTradeGate
    from app.modules.compliance.repository import (
        RuleRepository,
        ViolationRepository,
    )
    from app.modules.compliance.seed import build_seed_compliance_rules
    from app.modules.compliance.service import ComplianceService

    rule_repo = RuleRepository(session_factory)
    violation_repo = ViolationRepository(session_factory)
    position_service = fastapi_app.state.position_service
    security_master = fastapi_app.state.security_master_service

    pre_trade_gate = PreTradeGate(
        rule_repo=rule_repo,
        position_service=position_service,
        security_master=security_master,
    )

    audit_repo = fastapi_app.state.audit_repo
    compliance_service = ComplianceService(
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        pre_trade_gate=pre_trade_gate,
        audit_repo=audit_repo,
        position_service=position_service,
        security_master=security_master,
    )
    fastapi_app.state.compliance_service = compliance_service

    # Post-trade monitor: subscribe to positions.changed for each fund
    post_trade_monitor = PostTradeMonitor(
        session_factory=session_factory,
        position_service=position_service,
        security_master=security_master,
        event_bus=event_bus,
    )
    active_funds = await fund_repo.get_all_active()
    for fund in active_funds:
        topic = fund_topic(fund.slug, "positions.changed")
        event_bus.subscribe(topic, post_trade_monitor.handle_position_changed)
        # Also subscribe to MTM events to detect passive breaches / auto-resolve
        pnl_topic = fund_topic(fund.slug, "pnl.updated")
        event_bus.subscribe(pnl_topic, post_trade_monitor.handle_mtm_update)
    logger.info("post_trade_monitor_subscribed", fund_count=len(active_funds))

    # Seed default compliance rules for each fund (needs fund-scoped sessions)
    for fund in active_funds:
        fund_rule_repo = RuleRepository(session_factory, fund_slug=fund.slug)
        existing = await fund_rule_repo.get_all_by_fund(fund.slug)
        if not existing:
            rules = build_seed_compliance_rules(fund.slug)
            for rule in rules:
                await fund_rule_repo.insert(rule)
            logger.info(
                "compliance_rules_seeded",
                fund_slug=fund.slug,
                count=len(rules),
            )

    # Startup compliance scan: resolve ALL existing violations, then
    # re-evaluate every portfolio with current data.  This prevents stale
    # violations from prior runs (created when positions were partially
    # loaded or when the monitor had errors).
    from uuid import UUID as _UUID

    portfolio_repo: PortfolioRepository = fastapi_app.state.portfolio_repo
    scanned = 0
    for fund in active_funds:
        fund_viol_repo = ViolationRepository(session_factory, fund_slug=fund.slug)
        portfolios = await portfolio_repo.get_by_fund(str(fund.id))
        for portfolio in portfolios:
            pid = _UUID(portfolio.id)
            # Clear all active violations so the scan starts fresh
            stale = await fund_viol_repo.get_active_by_portfolio(pid)
            for v in stale:
                await fund_viol_repo.resolve(
                    _UUID(v.id), resolved_by="system_startup", resolution_type="auto",
                )
            try:
                # Re-evaluate — creates violations only for actual breaches
                await post_trade_monitor._evaluate_portfolio(
                    pid, fund.slug, is_passive=True,
                )
                scanned += 1
            except Exception:
                logger.warning(
                    "compliance_startup_scan_portfolio_failed",
                    portfolio_id=portfolio.id,
                    fund_slug=fund.slug,
                    exc_info=True,
                )
    logger.info("compliance_startup_scan_complete", portfolios_scanned=scanned)


async def setup_risk_engine(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    event_bus: EventBus | None = None,
    fund_repo: FundRepository | None = None,
) -> None:
    """Wire risk engine module: repo, service, event subscriptions."""
    from app.modules.risk_engine.repository import RiskRepository
    from app.modules.risk_engine.service import RiskService

    risk_repo = RiskRepository(session_factory)
    position_service = fastapi_app.state.position_service
    market_data_service = fastapi_app.state.market_data_service
    sm_service = fastapi_app.state.security_master_service
    risk_service = RiskService(
        risk_repo=risk_repo,
        position_service=position_service,
        market_data_service=market_data_service,
        security_master_service=sm_service,
        event_bus=event_bus,
    )
    fastapi_app.state.risk_service = risk_service

    # Subscribe: recalculate risk when positions change
    if event_bus is not None and fund_repo is not None:
        active_funds = await fund_repo.get_all_active()
        for fund in active_funds:

            def _make_handler(slug: str):  # type: ignore[no-untyped-def]
                async def on_position_changed(event: BaseEvent) -> None:
                    pid_str = event.data.get("portfolio_id")
                    if not pid_str:
                        return
                    from uuid import UUID

                    try:
                        await risk_service.take_snapshot(
                            UUID(pid_str),
                            fund_slug=slug,
                        )
                    except Exception:
                        logger.exception(
                            "risk_reactive_snapshot_failed",
                            portfolio_id=pid_str,
                        )

                return on_position_changed

            event_bus.subscribe(
                fund_topic(fund.slug, "positions.changed"),
                _make_handler(fund.slug),
            )
        logger.info(
            "risk_subscribed_to_positions",
            fund_count=len(active_funds),
        )


async def setup_cash_management(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    event_bus: EventBus,
    fund_repo: FundRepository,
) -> None:
    """Wire cash management module: repos, service, event subscriptions."""
    from app.modules.cash_management.repository import (
        CashBalanceRepository,
        CashJournalRepository,
        CashProjectionRepository,
        ScheduledFlowRepository,
        SettlementRepository,
    )
    from app.modules.cash_management.service import CashManagementService

    sm_service = fastapi_app.state.security_master_service
    cash_service = CashManagementService(
        balance_repo=CashBalanceRepository(session_factory),
        journal_repo=CashJournalRepository(session_factory),
        settlement_repo=SettlementRepository(session_factory),
        scheduled_flow_repo=ScheduledFlowRepository(session_factory),
        projection_repo=CashProjectionRepository(session_factory),
        security_master_service=sm_service,
        event_bus=event_bus,
    )
    fastapi_app.state.cash_service = cash_service

    # Subscribe to trades.executed for automatic settlement creation
    active_funds = await fund_repo.get_all_active()
    for fund in active_funds:
        topic = fund_topic(fund.slug, "trades.executed")
        event_bus.subscribe(topic, cash_service.handle_trade_executed)
    logger.info("cash_management_subscribed", fund_count=len(active_funds))


async def setup_attribution(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
) -> None:
    """Wire attribution module: repo, service."""
    from app.modules.attribution.repository import AttributionRepository
    from app.modules.attribution.service import AttributionService

    attribution_repo = AttributionRepository(session_factory)
    position_service = fastapi_app.state.position_service
    sm_service = fastapi_app.state.security_master_service
    attribution_service = AttributionService(
        attribution_repo=attribution_repo,
        position_service=position_service,
        security_master_service=sm_service,
    )
    fastapi_app.state.attribution_service = attribution_service


async def setup_alpha_engine(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
) -> None:
    """Wire alpha engine module: repo, service."""
    from app.modules.alpha_engine.repository import AlphaRepository
    from app.modules.alpha_engine.service import AlphaService

    alpha_repo = AlphaRepository(session_factory)
    position_service = fastapi_app.state.position_service
    sm_service = fastapi_app.state.security_master_service
    alpha_service = AlphaService(
        alpha_repo=alpha_repo,
        position_service=position_service,
        security_master_service=sm_service,
    )
    fastapi_app.state.alpha_service = alpha_service


async def setup_orders(
    fastapi_app: FastAPI,
    session_factory: TenantSessionFactory,
    event_bus: EventBus,
    broker: BrokerAdapter,
) -> None:
    """Wire orders module: repo, compliance gateway, broker, service."""
    from app.modules.orders.compliance_gateway import ComplianceGateway
    from app.modules.orders.repository import OrderRepository
    from app.modules.orders.service import OrderService

    order_repo = OrderRepository(session_factory)
    compliance_service = fastapi_app.state.compliance_service
    compliance_gateway = ComplianceGateway(compliance_service.pre_trade_gate)
    audit_repo = fastapi_app.state.audit_repo
    order_service = OrderService(
        order_repo=order_repo,
        compliance_gateway=compliance_gateway,
        broker=broker,
        event_bus=event_bus,
        audit_repo=audit_repo,
    )
    fastapi_app.state.order_service = order_service


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _make_price_handler(market_data_service: MarketDataService):  # type: ignore[no-untyped-def]
    """Create a price event handler bound to the given service."""

    _required_fields = ("instrument_id", "bid", "ask", "mid", "source")

    async def on_price_event(event: BaseEvent) -> None:
        try:
            data = event.data
            if not all(k in data for k in _required_fields):
                logger.warning(
                    "price_event_missing_fields",
                    event_id=event.event_id,
                    keys=list(data.keys()),
                )
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
            market_data_service.update_latest(snapshot)
            await market_data_service.store_price(snapshot)
        except Exception:
            logger.exception("price_event_handler_failed", event_id=event.event_id)

    return on_price_event
