"""Temporal DTOs — serializable across the Temporal boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EodInput:
    """Input for the EOD workflow."""

    fund_slug: str
    business_date: str  # ISO format, e.g. "2024-01-15"


@dataclass
class StepResult:
    """Result of a single EOD step."""

    step: str
    success: bool
    details: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class EodResult:
    """Aggregate result of the full EOD run."""

    fund_slug: str
    business_date: str
    steps: list[StepResult]
    is_successful: bool
