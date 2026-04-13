"""EOD processing module wiring — orchestrator, services, repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.eod.core.nav_calculator import NAVCalculator
from app.modules.eod.core.orchestrator import EODOrchestrator
from app.modules.eod.core.pnl_snapshot import PnLSnapshotService
from app.modules.eod.core.price_finalization import PriceFinalizationService
from app.modules.eod.core.reconciler import PositionReconciler
from app.modules.eod.repositories import (
    EODRunRepository,
    FinalizedPriceRepository,
    NAVSnapshotRepository,
    PnLSnapshotRepository,
    ReconciliationBreakRepository,
    ReconciliationRepository,
)
from app.modules.positions.repositories.daily_pnl import DailyPnLRepository

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.adapters.broker import BrokerAdapter
    from app.shared.adapters.fund_admin import FundAdminAdapter
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> None:
    """Wire EOD processing module: orchestrator, services, repositories."""
    broker: BrokerAdapter = ctx["broker"]
    fund_admin: FundAdminAdapter | None = ctx.get("fund_admin")

    run_repo = EODRunRepository(sf)
    price_repo = FinalizedPriceRepository(sf)
    nav_repo = NAVSnapshotRepository(sf)
    pnl_repo = PnLSnapshotRepository(sf)
    recon_repo = ReconciliationRepository(sf)
    break_repo = ReconciliationBreakRepository(sf)

    position_service = app.state.position_service
    cash_service = app.state.cash_service
    market_data_service = app.state.market_data_service
    sm_service = app.state.security_master_service
    risk_service = app.state.risk_snapshot_service
    fund_repo = app.state.fund_repo
    portfolio_repo = app.state.portfolio_repo
    fee_service = getattr(app.state, "fee_accounting_service", None)
    capital_service = getattr(app.state, "capital_account_service", None)
    capital_transaction_service = getattr(app.state, "capital_transaction_service", None)
    attribution_service = getattr(app.state, "attribution_service", None)

    price_service = PriceFinalizationService(
        price_repo=price_repo,
        market_data_service=market_data_service,
        security_master_service=sm_service,
    )
    fx_converter = market_data_service.fx_converter

    nav_calculator = NAVCalculator(
        position_service=position_service,
        cash_service=cash_service,
        nav_repo=nav_repo,
        fee_service=fee_service,
        capital_service=capital_service,
        fx_converter=fx_converter,
    )
    daily_pnl_repo = DailyPnLRepository(sf)
    pnl_service = PnLSnapshotService(
        position_service=position_service,
        pnl_repo=pnl_repo,
        daily_pnl_repo=daily_pnl_repo,
        fx_converter=fx_converter,
    )
    reconciler = PositionReconciler(
        position_service=position_service,
        broker_adapter=broker,
        recon_repo=recon_repo,
        break_repo=break_repo,
        fund_admin_adapter=fund_admin,
        cash_service=cash_service,
    )
    app.state.nav_snapshot_repo = nav_repo
    app.state.recon_repo = recon_repo
    app.state.break_repo = break_repo

    orchestrator = EODOrchestrator(
        run_repo=run_repo,
        fund_repo=fund_repo,
        portfolio_repo=portfolio_repo,
        price_service=price_service,
        nav_calculator=nav_calculator,
        pnl_service=pnl_service,
        reconciler=reconciler,
        risk_service=risk_service,
        fee_service=fee_service,
        capital_service=capital_service,
        capital_transaction_service=capital_transaction_service,
        attribution_service=attribution_service,
        subscription_service=getattr(app.state, "subscription_service", None),
        redemption_service=getattr(app.state, "redemption_service", None),
    )
    app.state.eod_orchestrator = orchestrator
    logger.info("eod_module_ready")

    import os

    if os.environ.get("APP_ENV", "local") == "local":
        try:
            from app.modules.eod.seed import seed_dev_data

            await seed_dev_data(app, sf)
        except Exception:
            pass
