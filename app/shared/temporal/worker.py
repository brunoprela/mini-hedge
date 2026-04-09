"""Temporal worker factory."""

from __future__ import annotations

from collections.abc import Callable

from temporalio.worker import Worker

from app.shared.temporal.client import get_temporal_client


async def create_worker(
    task_queue: str,
    workflows: list[type],
    activities: list[Callable],
) -> Worker:
    """Create a Temporal worker with standard configuration."""
    client = await get_temporal_client()
    return Worker(
        client,
        task_queue=task_queue,
        workflows=workflows,
        activities=activities,
    )


async def run_worker(
    task_queue: str,
    workflows: list[type],
    activities: list[Callable],
) -> None:
    """Create and run a Temporal worker (blocks until shutdown)."""
    worker = await create_worker(task_queue, workflows, activities)
    await worker.run()
