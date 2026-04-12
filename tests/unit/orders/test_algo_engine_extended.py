"""Extended AlgoEngine tests — recover_active_algos and cancel with children."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.orders.core.algo_engine import AlgoEngine


def _make_parent(
    algo_type: str = "twap",
    quantity: Decimal = Decimal("1000"),
    algo_params: dict | None = None,
    order_id: str | None = None,
    fund_slug: str = "test-fund",
) -> MagicMock:
    p = MagicMock()
    p.id = order_id or str(uuid4())
    p.algo_type = algo_type
    p.quantity = quantity
    p.algo_params = algo_params or {"duration_seconds": 60, "num_slices": 5}
    p.fund_slug = fund_slug
    return p


def _make_engine() -> tuple[AlgoEngine, AsyncMock]:
    order_repo = AsyncMock()
    order_repo.get_active_children = AsyncMock(return_value=[])
    order_repo.get_working_parents = AsyncMock(return_value=[])
    order_repo.get_children = AsyncMock(return_value=[])
    engine = AlgoEngine(order_repo=order_repo)
    return engine, order_repo


class TestRecoverActiveAlgos:
    async def test_recovers_working_parents(self) -> None:
        engine, order_repo = _make_engine()

        parent_id = str(uuid4())
        parent = _make_parent(order_id=parent_id)
        order_repo.get_working_parents.return_value = [parent]
        order_repo.get_children.return_value = [MagicMock(), MagicMock()]  # 2 existing children

        await engine.recover_active_algos(["fund-alpha"])

        order_repo.get_working_parents.assert_awaited()
        order_repo.get_children.assert_awaited()
        # Runner should have been created then restarted
        # After recovery, the runner for parent-1 should exist
        # (start_algo creates it, then cancel+restart with resume_from)

    async def test_recovers_with_no_working_parents(self) -> None:
        engine, order_repo = _make_engine()
        order_repo.get_working_parents.return_value = []

        await engine.recover_active_algos(["fund-alpha"])

        order_repo.get_working_parents.assert_awaited()
        order_repo.get_children.assert_not_awaited()

    async def test_recovery_handles_exception(self) -> None:
        engine, order_repo = _make_engine()
        order_repo.get_working_parents.side_effect = RuntimeError("DB error")

        # Should not raise — exception is caught and logged
        await engine.recover_active_algos(["fund-alpha"])

    async def test_recovers_multiple_funds(self) -> None:
        engine, order_repo = _make_engine()

        parent1 = _make_parent(order_id=str(uuid4()), fund_slug="alpha")
        parent2 = _make_parent(order_id=str(uuid4()), fund_slug="beta")

        call_count = 0

        async def mock_working_parents(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [parent1]
            return [parent2]

        order_repo.get_working_parents.side_effect = mock_working_parents
        order_repo.get_children.return_value = []

        await engine.recover_active_algos(["alpha", "beta"])

        assert order_repo.get_working_parents.await_count == 2


class TestCancelAlgoWithActiveChildren:
    async def test_cancel_iterates_active_children(self) -> None:
        engine, order_repo = _make_engine()
        parent = _make_parent()
        await engine.start_algo(parent, "test-fund")

        child1 = MagicMock()
        child1.id = str(uuid4())
        child2 = MagicMock()
        child2.id = str(uuid4())
        order_repo.get_active_children.return_value = [child1, child2]

        await engine.cancel_algo(UUID(parent.id))

        order_repo.get_active_children.assert_awaited_once()
        assert parent.id not in engine._runners
