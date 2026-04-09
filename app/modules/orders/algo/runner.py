"""Algo runner — long-lived asyncio task that submits child orders on schedule."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from app.modules.orders.algo.strategies import ChildSlice
    from app.modules.orders.models.order import OrderRecord


class SubmitChildCallback(Protocol):
    async def __call__(
        self,
        *,
        parent_order_id: str,
        quantity: Decimal,
        fund_slug: str,
        limit_price: Decimal | None,
    ) -> None: ...


OnCompleteCallback = Callable[[str], Awaitable[None]]

logger = structlog.get_logger()


class AlgoRunner:
    """Manages the lifecycle of a single algo order's child submissions.

    TWAP/VWAP: time-driven — sleeps between slices.
    Iceberg: fill-driven — waits for on_child_filled callback.
    """

    def __init__(
        self,
        *,
        parent_order_id: str,
        fund_slug: str,
        slices: list[ChildSlice],
        is_fill_driven: bool,
        submit_child: SubmitChildCallback,
        on_complete: OnCompleteCallback,
    ) -> None:
        self._parent_order_id = parent_order_id
        self._fund_slug = fund_slug
        self._slices = slices
        self._is_fill_driven = is_fill_driven
        self._submit_child = submit_child
        self._on_complete = on_complete

        self._task: asyncio.Task[None] | None = None
        self._cancelled = False
        self._current_slice_index = 0
        self._pending_fill_event = asyncio.Event()

    @property
    def is_active(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def slices_submitted(self) -> int:
        return self._current_slice_index

    async def start(self, *, resume_from: int = 0) -> None:
        self._current_slice_index = resume_from
        self._task = asyncio.create_task(self._run())
        # prevent GC of the task
        self._task.add_done_callback(lambda _: None)

    async def _run(self) -> None:
        log = logger.bind(
            parent_order_id=self._parent_order_id,
            fund_slug=self._fund_slug,
            total_slices=len(self._slices),
        )
        try:
            start_time = asyncio.get_event_loop().time()

            for i in range(self._current_slice_index, len(self._slices)):
                if self._cancelled:
                    log.info("algo_runner_cancelled", slices_submitted=i)
                    break

                child_slice = self._slices[i]

                if self._is_fill_driven and i > 0:
                    # Iceberg: wait for previous child to fill
                    self._pending_fill_event.clear()
                    try:
                        await asyncio.wait_for(
                            self._pending_fill_event.wait(),
                            timeout=300,  # 5 min timeout per slice
                        )
                    except TimeoutError:
                        log.warning("algo_iceberg_timeout", slice_index=i)
                        break
                else:
                    # TWAP/VWAP: sleep until scheduled time
                    target_time = start_time + child_slice.delay_seconds
                    now = asyncio.get_event_loop().time()
                    if target_time > now:
                        await asyncio.sleep(target_time - now)

                if self._cancelled:
                    break

                try:
                    await self._submit_child(
                        parent_order_id=self._parent_order_id,
                        quantity=child_slice.quantity,
                        fund_slug=self._fund_slug,
                        limit_price=child_slice.limit_price,
                    )
                    self._current_slice_index = i + 1
                except Exception:
                    log.exception("algo_child_submit_failed", slice_index=i)
                    # Continue with next slice rather than aborting
                    self._current_slice_index = i + 1

            log.info(
                "algo_runner_finished",
                slices_submitted=self._current_slice_index,
                cancelled=self._cancelled,
            )
        except asyncio.CancelledError:
            log.info("algo_runner_task_cancelled")
        except Exception:
            log.exception("algo_runner_error")
        finally:
            await self._on_complete(self._parent_order_id)

    async def on_child_filled(self, child: OrderRecord) -> None:
        """Called when a child order receives a fill. Triggers next Iceberg slice."""
        if self._is_fill_driven:
            self._pending_fill_event.set()

    async def cancel(self) -> None:
        self._cancelled = True
        self._pending_fill_event.set()  # unblock any waiting
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
