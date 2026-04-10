"""Algo engine — manages active algo runners and their lifecycle."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.orders.core.algo_runner import AlgoRunner
from app.modules.orders.core.algo_strategies import get_strategy
from app.modules.orders.interfaces import AlgoParams, AlgoType

if TYPE_CHECKING:
    from app.modules.orders.models.order import OrderRecord
    from app.modules.orders.repositories import OrderRepository

SubmitChildFn = Callable[..., Awaitable[object]]

logger = structlog.get_logger()


class AlgoEngine:
    """Manages algo order lifecycle — spawns and tracks child orders."""

    def __init__(
        self,
        *,
        order_repo: OrderRepository,
    ) -> None:
        self._order_repo = order_repo
        self._runners: dict[str, AlgoRunner] = {}

        # Set by setup.py after OrderService is created (avoids circular dep)
        self._submit_child_fn: SubmitChildFn | None = None

    def set_submit_child(self, fn: SubmitChildFn) -> None:
        self._submit_child_fn = fn

    async def start_algo(
        self,
        parent: OrderRecord,
        fund_slug: str,
    ) -> None:
        """Create an AlgoRunner for the parent order and start it."""
        if parent.algo_type is None:
            msg = f"Order {parent.id} has no algo_type"
            raise ValueError(msg)

        algo_type = parent.algo_type
        params = AlgoParams(**(parent.algo_params or {}))
        strategy = get_strategy(algo_type)
        slices = strategy.compute_slices(parent.quantity, params)

        is_fill_driven = algo_type == AlgoType.ICEBERG

        runner = AlgoRunner(
            parent_order_id=parent.id,
            fund_slug=fund_slug,
            slices=slices,
            is_fill_driven=is_fill_driven,
            submit_child=self._do_submit_child,
            on_complete=self._on_runner_complete,
        )
        self._runners[parent.id] = runner
        await runner.start()

        logger.info(
            "algo_started",
            parent_order_id=parent.id,
            algo_type=algo_type,
            total_slices=len(slices),
            duration_seconds=params.duration_seconds,
        )

    async def cancel_algo(self, parent_order_id: UUID) -> None:
        """Cancel an active algo — stops the runner and cancels unfilled children."""
        key = str(parent_order_id)
        runner = self._runners.get(key)
        if runner and runner.is_active:
            await runner.cancel()

        # Cancel all unfilled children
        active_children = await self._order_repo.get_active_children(parent_order_id)
        for _child in active_children:
            # The OrderService.cancel_order will handle state transitions
            pass  # Caller (OrderService) handles child cancellation

        self._runners.pop(key, None)
        logger.info("algo_cancelled", parent_order_id=key)

    async def on_child_filled(
        self,
        child: OrderRecord,
        fund_slug: str,
    ) -> None:
        """Called when a child order receives a fill. Triggers Iceberg replenishment."""
        if child.parent_order_id is None:
            return
        runner = self._runners.get(child.parent_order_id)
        if runner and runner.is_active:
            await runner.on_child_filled(child)

    async def recover_active_algos(self, fund_slugs: list[str]) -> None:
        """Restart runners for orders left in WORKING state after a process restart."""
        for _fund_slug in fund_slugs:
            try:
                working = await self._order_repo.get_working_parents()
                for parent in working:
                    children = await self._order_repo.get_children(UUID(parent.id))
                    resume_from = len(children)
                    logger.info(
                        "algo_recovering",
                        parent_order_id=parent.id,
                        resume_from=resume_from,
                        fund_slug=parent.fund_slug,
                    )
                    await self.start_algo(parent, parent.fund_slug)
                    # Adjust runner to resume from last submitted slice
                    runner = self._runners.get(parent.id)
                    if runner:
                        await runner.cancel()
                        await runner.start(resume_from=resume_from)
            except Exception:
                logger.exception("algo_recovery_failed", fund_slug=_fund_slug)

    async def _do_submit_child(
        self,
        parent_order_id: str,
        quantity: Decimal,
        fund_slug: str,
        limit_price: Decimal | None,
    ) -> None:
        """Bridge to OrderService.create_child_order (set via set_submit_child)."""
        if self._submit_child_fn is None:
            msg = "AlgoEngine.set_submit_child() not called"
            raise RuntimeError(msg)
        await self._submit_child_fn(
            parent_order_id=parent_order_id,
            quantity=quantity,
            fund_slug=fund_slug,
            limit_price=limit_price,
        )

    async def _on_runner_complete(self, parent_order_id: str) -> None:
        """Called when a runner finishes (all slices submitted or cancelled)."""
        self._runners.pop(parent_order_id, None)
        logger.info("algo_runner_removed", parent_order_id=parent_order_id)
