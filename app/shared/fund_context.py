"""Fund context propagation via contextvars.

Every request operates within a fund context. The fund slug flows through
all layers without being manually threaded through function arguments.
contextvars is async-safe and scoped to the current task.
"""

from __future__ import annotations

from contextvars import ContextVar

_current_fund: ContextVar[str] = ContextVar("current_fund")

# Default fund for Phase 0 — single-fund deployment
DEFAULT_FUND_SLUG = "fund-alpha"


def get_current_fund() -> str:
    """Get the current fund slug. Falls back to default if not set."""
    return _current_fund.get(DEFAULT_FUND_SLUG)


def set_current_fund(fund_slug: str) -> None:
    """Set the current fund slug for this async context."""
    _current_fund.set(fund_slug)
