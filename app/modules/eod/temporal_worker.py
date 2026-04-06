"""Temporal worker for EOD workflows.

Runs as a standalone process (or as a Docker service) that polls the
``minihedge-eod`` task queue and executes EOD activities.

Start manually::

    python -m app.modules.eod.temporal_worker

Or via Docker Compose as the ``temporal-worker`` service.
"""

from __future__ import annotations

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from app.config import get_settings
from app.modules.eod.workflows import (
    EodWorkflow,
    calculate_attribution,
    calculate_nav,
    calculate_pnl,
    calculate_risk,
    close_market,
    finalize_prices,
    reconcile_positions,
)

logger = structlog.get_logger()

TASK_QUEUE = "minihedge-eod"


async def run_worker() -> None:
    """Connect to Temporal and start the EOD worker."""
    settings = get_settings()
    temporal_address = f"{settings.temporal_host}:{settings.temporal_port}"

    client = await Client.connect(temporal_address)

    worker = Worker(
        client,
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
    )

    logger.info(
        "temporal_worker_started",
        task_queue=TASK_QUEUE,
        address=temporal_address,
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
