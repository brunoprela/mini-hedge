"""Standard Temporal retry/timeout configuration."""

from __future__ import annotations

from datetime import timedelta

from temporalio.common import RetryPolicy

DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=3,
    backoff_coefficient=2.0,
)

DEFAULT_ACTIVITY_TIMEOUT = timedelta(minutes=10)
