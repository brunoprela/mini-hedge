"""Unit tests for AlgoRunner — async child order submission for TWAP/VWAP/Iceberg."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.orders.core.algo_runner import AlgoRunner
from app.modules.orders.core.algo_strategies import ChildSlice


def _make_slices(n: int = 3, qty: Decimal = Decimal("100")) -> list[ChildSlice]:
    return [
        ChildSlice(quantity=qty, delay_seconds=0.0, limit_price=None)
        for _ in range(n)
    ]


def _make_runner(
    slices: list[ChildSlice] | None = None,
    is_fill_driven: bool = False,
) -> tuple[AlgoRunner, AsyncMock, AsyncMock]:
    submit = AsyncMock()
    on_complete = AsyncMock()
    runner = AlgoRunner(
        parent_order_id="order-1",
        fund_slug="test-fund",
        slices=slices or _make_slices(),
        is_fill_driven=is_fill_driven,
        submit_child=submit,
        on_complete=on_complete,
    )
    return runner, submit, on_complete


class TestAlgoRunnerProperties:
    def test_not_active_before_start(self) -> None:
        runner, _, _ = _make_runner()
        assert not runner.is_active

    def test_slices_submitted_starts_at_zero(self) -> None:
        runner, _, _ = _make_runner()
        assert runner.slices_submitted == 0


class TestTimeDrivenRunner:
    @pytest.mark.asyncio
    async def test_submits_all_slices(self) -> None:
        slices = _make_slices(3, Decimal("100"))
        runner, submit, on_complete = _make_runner(slices=slices)

        await runner.start()
        await asyncio.sleep(0.05)  # let the task run
        # Wait for task to complete
        if runner._task:
            await runner._task

        assert submit.call_count == 3
        on_complete.assert_called_once_with("order-1")

    @pytest.mark.asyncio
    async def test_cancel_stops_execution(self) -> None:
        # Many slices with small delays
        slices = [
            ChildSlice(quantity=Decimal("10"), delay_seconds=i * 0.5, limit_price=None)
            for i in range(20)
        ]
        runner, submit, on_complete = _make_runner(slices=slices)

        await runner.start()
        await asyncio.sleep(0.05)
        await runner.cancel()

        # Should have submitted fewer than 20 slices
        assert submit.call_count < 20
        assert not runner.is_active

    @pytest.mark.asyncio
    async def test_submit_failure_continues(self) -> None:
        """A failed child submission should not abort the runner."""
        slices = _make_slices(3, Decimal("100"))
        runner, submit, on_complete = _make_runner(slices=slices)
        submit.side_effect = [RuntimeError("fail"), None, None]

        await runner.start()
        if runner._task:
            await runner._task

        # All 3 attempted despite first failing
        assert submit.call_count == 3
        on_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_from(self) -> None:
        slices = _make_slices(5, Decimal("100"))
        runner, submit, on_complete = _make_runner(slices=slices)

        await runner.start(resume_from=3)
        if runner._task:
            await runner._task

        # Should only submit slices 3, 4
        assert submit.call_count == 2


class TestFillDrivenRunner:
    @pytest.mark.asyncio
    async def test_iceberg_waits_for_fill(self) -> None:
        slices = _make_slices(3, Decimal("100"))
        runner, submit, on_complete = _make_runner(slices=slices, is_fill_driven=True)

        await runner.start()
        await asyncio.sleep(0.05)

        # First slice submitted immediately; second waits for fill
        assert submit.call_count == 1

        # Simulate fill
        child = MagicMock()
        await runner.on_child_filled(child)
        await asyncio.sleep(0.05)
        assert submit.call_count == 2

        # Third slice
        await runner.on_child_filled(child)
        await asyncio.sleep(0.05)

        if runner._task:
            await runner._task

        assert submit.call_count == 3
        on_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_iceberg_cancel_unblocks_wait(self) -> None:
        slices = _make_slices(5, Decimal("100"))
        runner, submit, on_complete = _make_runner(slices=slices, is_fill_driven=True)

        await runner.start()
        await asyncio.sleep(0.05)
        assert submit.call_count == 1

        # Cancel while waiting for fill
        await runner.cancel()
        assert not runner.is_active

    @pytest.mark.asyncio
    async def test_on_child_filled_noop_when_not_fill_driven(self) -> None:
        runner, _, _ = _make_runner(is_fill_driven=False)
        child = MagicMock()
        # Should not raise
        await runner.on_child_filled(child)
