"""Centralized router registry — one place to see every API route."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

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
from app.modules.orders.allocation.routes import router as allocation_router
from app.modules.orders.broker_routes import router as broker_router
from app.modules.orders.routes import router as orders_router
from app.modules.orders.tca.routes import router as tca_router
from app.modules.platform.admin_routes import router as admin_router
from app.modules.platform.routes import router as platform_router
from app.modules.positions.routes import router as positions_router
from app.modules.quant_research.routes import router as quant_research_router
from app.modules.realtime.routes import router as realtime_router
from app.modules.regulatory.routes import router as regulatory_router
from app.modules.risk_engine.routes import router as risk_router
from app.modules.security_master.routes import router as security_master_router

ALL_ROUTERS = [
    platform_router,
    admin_router,
    security_master_router,
    market_data_router,
    fx_router,
    positions_router,
    realtime_router,
    exposure_router,
    compliance_router,
    orders_router,
    risk_router,
    cash_router,
    attribution_router,
    alpha_router,
    eod_router,
    recon_router,
    fee_router,
    capital_router,
    corporate_actions_router,
    allocation_router,
    broker_router,
    tca_router,
    fx_hedging_router,
    investor_ops_router,
    regulatory_router,
    fund_structures_router,
    backtesting_router,
    quant_research_router,
    ai_analysis_router,
    alt_data_router,
    feature_store_router,
]


def register_all(app: FastAPI, prefix: str = "/api/v1") -> None:
    """Register all module routers on the FastAPI app."""
    for router in ALL_ROUTERS:
        app.include_router(router, prefix=prefix)
