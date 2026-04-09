"""EOD processing module wiring — orchestrator, services, repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.eod.nav_calculator import NAVCalculator
from app.modules.eod.orchestrator import EODOrchestrator
from app.modules.eod.pnl_snapshot import PnLSnapshotService
from app.modules.eod.price_finalization import PriceFinalizationService
from app.modules.eod.reconciler import PositionReconciler
from app.modules.eod.repository import (
    EODRunRepository,
    FinalizedPriceRepository,
    NAVSnapshotRepository,
    PnLSnapshotRepository,
    ReconciliationBreakRepository,
    ReconciliationRepository,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.adapters import BrokerAdapter, FundAdminAdapter
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
    risk_service = app.state.risk_service
    fund_repo = app.state.fund_repo
    portfolio_repo = app.state.portfolio_repo
    fee_service = getattr(app.state, "fee_accounting_service", None)
    capital_service = getattr(app.state, "capital_account_service", None)
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
    pnl_service = PnLSnapshotService(
        position_service=position_service,
        pnl_repo=pnl_repo,
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
        attribution_service=attribution_service,
        investor_ops_service=getattr(app.state, "investor_ops_service", None),
    )
    app.state.eod_orchestrator = orchestrator
    logger.info("eod_module_ready")
