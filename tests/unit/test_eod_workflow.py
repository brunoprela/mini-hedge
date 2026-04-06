"""Unit tests for the Temporal EOD workflow definition."""

from __future__ import annotations

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.modules.eod.workflows import (
    EodInput,
    EodResult,
    EodWorkflow,
    StepResult,
    calculate_attribution,
    calculate_nav,
    calculate_pnl,
    calculate_risk,
    close_market,
    finalize_prices,
    reconcile_positions,
)

TASK_QUEUE = "test-eod"


@pytest.fixture
def eod_input() -> EodInput:
    return EodInput(fund_slug="alpha", business_date="2024-01-15")


class TestEodWorkflow:
    @pytest.mark.asyncio
    async def test_full_eod_run_succeeds(self, eod_input: EodInput) -> None:
        async with (
            await WorkflowEnvironment.start_time_skipping() as env,
            Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[EodWorkflow],
                activities=[
                    close_market,
                    finalize_prices,
                    reconcile_positions,
                    calculate_nav,
                    calculate_pnl,
                    calculate_risk,
                    calculate_attribution,
                ],
            ),
        ):
            result = await env.client.execute_workflow(
                EodWorkflow.run,
                eod_input,
                id="test-eod-run",
                task_queue=TASK_QUEUE,
            )

            assert isinstance(result, EodResult)
            assert result.is_successful
            assert result.fund_slug == "alpha"
            assert result.business_date == "2024-01-15"
            # 5 sequential + 2 parallel = 7 steps
            assert len(result.steps) == 7

    @pytest.mark.asyncio
    async def test_step_names_match_orchestrator_order(self, eod_input: EodInput) -> None:
        async with (
            await WorkflowEnvironment.start_time_skipping() as env,
            Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[EodWorkflow],
                activities=[
                    close_market,
                    finalize_prices,
                    reconcile_positions,
                    calculate_nav,
                    calculate_pnl,
                    calculate_risk,
                    calculate_attribution,
                ],
            ),
        ):
            result = await env.client.execute_workflow(
                EodWorkflow.run,
                eod_input,
                id="test-eod-steps",
                task_queue=TASK_QUEUE,
            )

            step_names = [s.step for s in result.steps]
            assert step_names[:5] == [
                "market_close",
                "price_finalization",
                "position_recon",
                "nav_calculation",
                "pnl_snapshot",
            ]
            # Risk and attribution run in parallel — order may vary
            assert set(step_names[5:]) == {"eod_risk", "performance_attribution"}


class TestStepResult:
    def test_success_result(self) -> None:
        r = StepResult(step="nav_calculation", success=True, details={"nav": "100M"})
        assert r.success
        assert r.error is None

    def test_failure_result(self) -> None:
        r = StepResult(step="pnl_snapshot", success=False, error="DB timeout")
        assert not r.success
        assert r.error == "DB timeout"
