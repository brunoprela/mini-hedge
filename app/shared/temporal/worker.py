"""Temporal worker factory."""

from __future__ import annotations

from collections.abc import Callable

from temporalio.client import Client
from temporalio.worker import Worker

from app.shared.temporal.client import TemporalClientFactory, get_temporal_client


async def create_worker(
    task_queue: str,
    workflows: list[type],
    activities: list[Callable],
    *,
    client: Client | None = None,
    client_factory: TemporalClientFactory | None = None,
) -> Worker:
    """Create a Temporal worker with standard configuration.

    Prefer passing an explicit ``client`` (from ``app.state``) or
    ``client_factory`` so the worker is testable without the module-level
    default factory.  Falls back to the legacy process-wide client when
    neither is supplied (used by standalone worker processes).
    """
    if client is None:
        if client_factory is not None:
            client = await client_factory.connect()
        else:
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
    *,
    client: Client | None = None,
    client_factory: TemporalClientFactory | None = None,
) -> None:
    """Create and run a Temporal worker (blocks until shutdown)."""
    worker = await create_worker(
        task_queue,
        workflows,
        activities,
        client=client,
        client_factory=client_factory,
    )
    await worker.run()
