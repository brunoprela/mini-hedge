"""Temporal worker for EOD workflows.

Runs as a standalone process (or as a Docker service) that polls the
``minihedge-eod`` task queue and executes EOD activities.

Start manually::

    python -m app.modules.eod.temporal.worker

Or via Docker Compose as the ``temporal-worker`` service.
"""

from __future__ import annotations

import asyncio

import structlog

from app.modules.eod.temporal.activities import (
    calculate_attribution,
    calculate_nav,
    calculate_pnl,
    calculate_risk,
    close_market,
    finalize_prices,
    reconcile_positions,
)
from app.modules.eod.temporal.workflows import EodWorkflow
from app.shared.temporal import run_worker as _run_worker

logger = structlog.get_logger()

TASK_QUEUE = "minihedge-eod"

ACTIVITIES = [
    close_market,
    finalize_prices,
    reconcile_positions,
    calculate_nav,
    calculate_pnl,
    calculate_risk,
    calculate_attribution,
]


async def start() -> None:
    """Start the EOD Temporal worker."""
    logger.info("temporal_worker_starting", task_queue=TASK_QUEUE)
    await _run_worker(
        task_queue=TASK_QUEUE,
        workflows=[EodWorkflow],
        activities=ACTIVITIES,
    )


if __name__ == "__main__":
    asyncio.run(start())
