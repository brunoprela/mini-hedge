"""Unit tests for AlgoEngine — algo order lifecycle management."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.orders.core.algo_engine import AlgoEngine
from app.modules.orders.interfaces import AlgoParams, AlgoType


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


class TestStartAlgo:
    @pytest.mark.asyncio
    async def test_starts_twap_runner(self) -> None:
        engine, _ = _make_engine()
        parent = _make_parent(algo_type="twap")

        await engine.start_algo(parent, "test-fund")

        assert parent.id in engine._runners
        runner = engine._runners[parent.id]
        assert runner.is_active

        # Cleanup
        await runner.cancel()

    @pytest.mark.asyncio
    async def test_starts_iceberg_runner(self) -> None:
        engine, _ = _make_engine()
        parent = _make_parent(
            algo_type="iceberg",
            algo_params={"duration_seconds": 60, "num_slices": 5, "visible_quantity": 100},
        )

        await engine.start_algo(parent, "test-fund")

        runner = engine._runners[parent.id]
        assert runner.is_active
        assert runner._is_fill_driven

        await runner.cancel()

    @pytest.mark.asyncio
    async def test_no_algo_type_raises(self) -> None:
        engine, _ = _make_engine()
        parent = _make_parent()
        parent.algo_type = None

        with pytest.raises(ValueError, match="no algo_type"):
            await engine.start_algo(parent, "test-fund")


class TestCancelAlgo:
    @pytest.mark.asyncio
    async def test_cancel_active_algo(self) -> None:
        engine, _ = _make_engine()
        parent = _make_parent()
        await engine.start_algo(parent, "test-fund")

        await engine.cancel_algo(UUID(parent.id))

        assert parent.id not in engine._runners

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_algo(self) -> None:
        engine, _ = _make_engine()
        # Should not raise
        await engine.cancel_algo(uuid4())


class TestOnChildFilled:
    @pytest.mark.asyncio
    async def test_triggers_iceberg_fill(self) -> None:
        engine, _ = _make_engine()
        parent = _make_parent(
            algo_type="iceberg",
            algo_params={"duration_seconds": 60, "num_slices": 5, "visible_quantity": 100},
        )
        await engine.start_algo(parent, "test-fund")

        child = MagicMock()
        child.parent_order_id = parent.id

        # Should trigger next slice without error
        await engine.on_child_filled(child, "test-fund")

        # Cleanup
        await engine._runners[parent.id].cancel()

    @pytest.mark.asyncio
    async def test_ignores_child_without_parent(self) -> None:
        engine, _ = _make_engine()
        child = MagicMock()
        child.parent_order_id = None

        # Should silently return
        await engine.on_child_filled(child, "test-fund")


class TestDoSubmitChild:
    @pytest.mark.asyncio
    async def test_submit_without_fn_raises(self) -> None:
        engine, _ = _make_engine()

        with pytest.raises(RuntimeError, match="set_submit_child"):
            await engine._do_submit_child("order-1", Decimal("100"), "fund", None)

    @pytest.mark.asyncio
    async def test_submit_with_fn_delegates(self) -> None:
        engine, _ = _make_engine()
        fn = AsyncMock()
        engine.set_submit_child(fn)

        await engine._do_submit_child("order-1", Decimal("100"), "fund", Decimal("150"))

        fn.assert_called_once_with(
            parent_order_id="order-1",
            quantity=Decimal("100"),
            fund_slug="fund",
            limit_price=Decimal("150"),
        )


class TestOnRunnerComplete:
    @pytest.mark.asyncio
    async def test_removes_runner_on_complete(self) -> None:
        engine, _ = _make_engine()
        engine._runners["order-1"] = MagicMock()

        await engine._on_runner_complete("order-1")

        assert "order-1" not in engine._runners

    @pytest.mark.asyncio
    async def test_remove_nonexistent_is_noop(self) -> None:
        engine, _ = _make_engine()
        # Should not raise
        await engine._on_runner_complete("nonexistent")
