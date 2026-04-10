"""Temporal workflow for automated EOD processing.

Maps 1:1 to the existing :class:`EODOrchestrator` step sequence but
gains durable execution, automatic retries, cron scheduling, and
visibility via Temporal Web UI.

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

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.modules.eod.temporal.activities import (
        calculate_attribution,
        calculate_nav,
        calculate_pnl,
        calculate_risk,
        close_market,
        finalize_prices,
        reconcile_positions,
    )
    from app.modules.eod.temporal.types import EodInput, EodResult, StepResult
    from app.shared.temporal.config import DEFAULT_ACTIVITY_TIMEOUT, DEFAULT_RETRY_POLICY


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
