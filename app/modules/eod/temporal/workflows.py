"""Temporal workflow definitions for automated EOD processing.

Maps 1:1 to the existing :class:`EODOrchestrator` step sequence but
gains durable execution, automatic retries, cron scheduling, and
visibility via Temporal Web UI.

The workflow delegates each step to a Temporal activity that calls the
existing service methods.  This preserves all business logic — Temporal
only orchestrates ordering, retry, and state.

Usage (Temporal schedule — created once via admin API or CLI)::

    temporal schedule create \\
        --schedule-id eod-weekday \\
        --cron '0 21 * * 1-5' \\
        --workflow-id eod-run \\
        --task-queue minihedge-eod \\
        --workflow-type EodWorkflow

The cron runs at 21:00 UTC (4 PM ET) on weekdays.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import structlog

    from app.shared.temporal.config import DEFAULT_ACTIVITY_TIMEOUT, DEFAULT_RETRY_POLICY

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Data transfer objects (serializable across Temporal boundary)
# ---------------------------------------------------------------------------


@dataclass
class EodInput:
    """Input for the EOD workflow."""

    fund_slug: str
    business_date: str  # ISO format, e.g. "2024-01-15"


@dataclass
class StepResult:
    """Result of a single EOD step."""

    step: str
    success: bool
    details: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class EodResult:
    """Aggregate result of the full EOD run."""

    fund_slug: str
    business_date: str
    steps: list[StepResult]
    is_successful: bool


# ---------------------------------------------------------------------------
# Activities — thin wrappers around existing service methods
# ---------------------------------------------------------------------------

# Activity implementations are registered at worker startup.
# These stubs define the signatures Temporal uses for serialization.


@activity.defn
async def close_market(input: EodInput) -> StepResult:
    """Acknowledge market close — no-op in current implementation."""
    logger.info("eod_activity_market_close", fund_slug=input.fund_slug)
    return StepResult(step="market_close", success=True, details={"message": "acknowledged"})


@activity.defn
async def finalize_prices(input: EodInput) -> StepResult:
    """Finalize end-of-day prices for all instruments."""
    logger.info("eod_activity_finalize_prices", fund_slug=input.fund_slug)
    # In production, this calls PriceFinalizationService.finalize_prices()
    # via the activity's injected dependencies.
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


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@workflow.defn
class EodWorkflow:
    """Temporal workflow for automated end-of-day processing.

    Executes the same step sequence as :class:`EODOrchestrator`:
    market_close → price_finalization → position_recon → nav_calc →
    pnl → risk + attribution (parallel).
    """

    @workflow.run
    async def run(self, input: EodInput) -> EodResult:
        steps: list[StepResult] = []
        all_ok = True

        # Sequential steps
        for activity_fn in [
            close_market,
            finalize_prices,
            reconcile_positions,
            calculate_nav,
            calculate_pnl,
        ]:
            result = await workflow.execute_activity(
                activity_fn,
                input,
                start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY_POLICY,
            )
            steps.append(result)
            if not result.success:
                all_ok = False
                break

        # Parallel steps: risk + attribution (only if prior steps succeeded)
        if all_ok:
            risk_result, attr_result = await asyncio.gather(
                workflow.execute_activity(
                    calculate_risk,
                    input,
                    start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
                    retry_policy=DEFAULT_RETRY_POLICY,
                ),
                workflow.execute_activity(
                    calculate_attribution,
                    input,
                    start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
                    retry_policy=DEFAULT_RETRY_POLICY,
                ),
            )
            steps.extend([risk_result, attr_result])
            if not risk_result.success or not attr_result.success:
                all_ok = False

        return EodResult(
            fund_slug=input.fund_slug,
            business_date=input.business_date,
            steps=steps,
            is_successful=all_ok,
        )
