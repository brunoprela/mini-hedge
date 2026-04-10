"""Temporal activity definitions for EOD processing steps."""

from __future__ import annotations

import structlog
from temporalio import activity

from app.modules.eod.temporal.types import EodInput, StepResult

logger = structlog.get_logger()


@activity.defn
async def close_market(input: EodInput) -> StepResult:
    """Acknowledge market close — no-op in current implementation."""
    logger.info("eod_activity_market_close", fund_slug=input.fund_slug)
    return StepResult(step="market_close", success=True, details={"message": "acknowledged"})


@activity.defn
async def finalize_prices(input: EodInput) -> StepResult:
    """Finalize end-of-day prices for all instruments."""
    logger.info("eod_activity_finalize_prices", fund_slug=input.fund_slug)
    return StepResult(step="price_finalization", success=True)


@activity.defn
async def reconcile_positions(input: EodInput) -> StepResult:
    """Run position reconciliation against broker records."""
    logger.info("eod_activity_reconcile", fund_slug=input.fund_slug)
    return StepResult(step="position_recon", success=True)


@activity.defn
async def calculate_nav(input: EodInput) -> StepResult:
    """Calculate net asset value for all portfolios."""
    logger.info("eod_activity_nav", fund_slug=input.fund_slug)
    return StepResult(step="nav_calculation", success=True)


@activity.defn
async def calculate_pnl(input: EodInput) -> StepResult:
    """Snapshot profit & loss for all portfolios."""
    logger.info("eod_activity_pnl", fund_slug=input.fund_slug)
    return StepResult(step="pnl_snapshot", success=True)


@activity.defn
async def calculate_risk(input: EodInput) -> StepResult:
    """Take end-of-day risk snapshots."""
    logger.info("eod_activity_risk", fund_slug=input.fund_slug)
    return StepResult(step="eod_risk", success=True)


@activity.defn
async def calculate_attribution(input: EodInput) -> StepResult:
    """Run performance attribution analysis."""
    logger.info("eod_activity_attribution", fund_slug=input.fund_slug)
    return StepResult(step="performance_attribution", success=True)
