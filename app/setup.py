"""Module wiring orchestrator and lifespan helpers.

Delegates to per-module ``wiring.py`` files for service construction.
Keeps migration runner, dev-seeding orchestration, and the phased
``setup_all()`` entry-point that ``main.py`` calls once.
"""

from __future__ import annotations

import asyncio
import importlib
import os
from typing import TYPE_CHECKING, Any

import structlog
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.config import Settings
    from app.shared.adapters.alt_data import AltDataProvider
    from app.shared.adapters.broker import BrokerAdapter
    from app.shared.adapters.fund_admin import FundAdminAdapter
    from app.shared.adapters.reference_data import ReferenceDataAdapter
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()

# Bounded contexts whose Alembic migrations run on startup.
# Positions are NOT here — each fund gets its own schema, created
# by ensure_all_fund_schemas() after platform seeding discovers active funds.
MIGRATION_CONTEXTS = [
    "platform",
    "security_master",
    "market_data",
    "eod",
    "backtesting",
    "quant_research",
    "ai_analysis",
    "alt_data",
    "feature_store",
]


# ---------------------------------------------------------------------------
# Migrations (always run)
# ---------------------------------------------------------------------------


def _run_migrations_sync() -> None:
    for ctx in MIGRATION_CONTEXTS:
        cfg = AlembicConfig("alembic.ini", ini_section=ctx)
        cfg.set_section_option(ctx, "script_location", f"app/modules/{ctx}/migrations")
        alembic_command.upgrade(cfg, "head")
        logger.info("migrations_applied", context=ctx)


async def _run_migrations() -> None:
    await asyncio.to_thread(_run_migrations_sync)


# ---------------------------------------------------------------------------
# Dev seeding — only runs when APP_ENV == "local"
# ---------------------------------------------------------------------------


def _is_local_env() -> bool:
    return os.environ.get("APP_ENV", "local") == "local"


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Run cross-cutting dev-environment seeding.  No-op when APP_ENV != 'local'.

    Individual modules handle their own seeding in their ``wiring.setup()``.
    This function covers platform + instrument seeding that must happen before
    module wiring.
    """
    if not _is_local_env():
        return

    from app.modules.platform.repositories import (
        APIKeyRepository,
        FundRepository,
        OperatorRepository,
        PortfolioRepository,
        UserRepository,
    )
    from app.modules.platform.wiring import _seed_platform
    from app.modules.security_master.repositories import InstrumentRepository
    from app.modules.security_master.wiring import _seed_instruments

    fund_repo = FundRepository(sf)
    portfolio_repo = PortfolioRepository(sf)
    user_repo = UserRepository(sf)
    operator_repo = OperatorRepository(sf)
    api_key_repo = APIKeyRepository(sf)
    instrument_repo = InstrumentRepository(sf)

    await _seed_platform(fund_repo, portfolio_repo, user_repo, operator_repo, api_key_repo)
    await _seed_instruments(instrument_repo)


# ---------------------------------------------------------------------------
# Module wiring orchestrator
# ---------------------------------------------------------------------------


async def _setup_module(name: str, app: FastAPI, sf: TenantSessionFactory, **kwargs: Any) -> Any:
    """Import and call a module's ``wiring.setup()``."""
    mod = importlib.import_module(f"app.modules.{name}.wiring")
    return await mod.setup(app, sf, **kwargs)


async def setup_all(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    engine: AsyncEngine,
    event_bus: EventBus,
    settings: Settings,
    broker: BrokerAdapter,
    broker_registry: object | None = None,
    reference_adapter: ReferenceDataAdapter | None = None,
    llm_adapter: object | None = None,
    alt_data_provider: AltDataProvider | None = None,
    fund_admin: FundAdminAdapter | None = None,
) -> list[str]:
    """Wire all modules in dependency order.

    Returns the list of active fund slugs (needed by bridge consumers in
    ``main.py``).
    """
    from app.modules.platform.wiring import setup_fga
    from app.shared.fund_schema import ensure_all_fund_schemas
    from app.shared.observability.logging import setup_logging
    from app.shared.schema_registry import fund_topics_for_slug, shared_topics

    # ── Phase 0: Foundation ──────────────────────────────────────────────
    # FGA must init before platform (AuthService depends on FGAClient)
    fga_client = await setup_fga(app, settings)

    await _setup_module(
        "platform",
        app,
        sf,
        event_bus=event_bus,
        settings=settings,
        fga_client=fga_client,
        engine=engine,
    )
    await _setup_module(
        "security_master",
        app,
        sf,
        reference_adapter=reference_adapter,
    )

    # Create per-fund schemas and run positions migrations for each
    fund_repo = app.state.fund_repo
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
    await event_bus.ensure_topics(all_topics + dlq_topics)

    # ── Phase 1: Core domain ─────────────────────────────────────────────
    sm_service = app.state.security_master_service
    await _setup_module("market_data", app, sf, event_bus=event_bus, settings=settings)
    await _setup_module(
        "positions",
        app,
        sf,
        event_bus=event_bus,
        settings=settings,
        fund_repo=fund_repo,
        security_master_service=sm_service,
    )
    logger.info("phase_1_modules_ready")

    # ── Phase 2: Exposure, compliance, orders ────────────────────────────
    await _setup_module(
        "exposure",
        app,
        sf,
        event_bus=event_bus,
        settings=settings,
        fund_repo=fund_repo,
    )
    await _setup_module(
        "compliance",
        app,
        sf,
        event_bus=event_bus,
        settings=settings,
        fund_repo=fund_repo,
    )
    await _setup_module(
        "orders",
        app,
        sf,
        event_bus=event_bus,
        settings=settings,
        broker=broker,
        broker_registry=broker_registry,
    )
    logger.info("phase_2_modules_ready")

    # ── Phase 3: Risk, accounting, operations, analytics, EOD ────────────
    logger.info("phase_3_starting")
    phase_3_modules: list[tuple[str, dict[str, Any]]] = [
        ("risk_engine", {}),
        ("cash_management", {"fund_repo": fund_repo}),
        ("attribution", {}),
        ("alpha_engine", {}),
        ("fee_accounting", {}),
        ("capital_accounts", {}),
        ("corporate_actions", {}),
        ("fx_hedging", {}),
        ("investor_operations", {}),
        ("regulatory", {}),
        ("fund_structures", {}),
        ("backtesting", {}),
        ("quant_research", {}),
        ("ai_analysis", {"llm_adapter": llm_adapter}),
        ("alt_data", {"alt_data_provider": alt_data_provider}),
        ("feature_store", {}),
        ("eod", {"broker": broker, "fund_admin": fund_admin}),
    ]
    for name, ctx in phase_3_modules:
        logger.info("setup_starting", module=name)
        await _setup_module(name, app, sf, event_bus=event_bus, settings=settings, **ctx)
        logger.info("setup_done", module=name)
    logger.info("phase_3_modules_ready")

    return fund_slugs
