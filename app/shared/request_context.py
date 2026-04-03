"""Request context propagation via contextvars.

Every request carries an actor context: who is acting, what kind of actor,
which fund they're operating in, and what they're allowed to do. This replaces
the simpler fund_context.py and serves as the single source of identity
for the entire request lifecycle.

contextvars is async-safe and scoped to the current task, so concurrent
requests never leak context.
"""

from __future__ import annotations

from contextvars import ContextVar
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActorType(StrEnum):
    USER = "user"
    API_KEY = "apikey"
    AGENT = "agent"
    SYSTEM = "system"


class RequestContext(BaseModel):
    """Immutable identity + authorization context for a single request."""

    model_config = ConfigDict(frozen=True)

    actor_id: str
    actor_type: ActorType
    fund_slug: str

    @field_validator("fund_slug")
    @classmethod
    def _fund_slug_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("fund_slug must not be empty")
        return v

    fund_id: str | None = None  # UUID of the fund, resolved during auth
    roles: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    delegated_by: str | None = None


_current_context: ContextVar[RequestContext] = ContextVar("request_context")

# Default fund for single-fund Phase 0 deployment
DEFAULT_FUND_SLUG = "alpha"

# System context used during startup (migrations, seeding) — not a request
SYSTEM_CONTEXT = RequestContext(
    actor_id="system",
    actor_type=ActorType.SYSTEM,
    fund_slug=DEFAULT_FUND_SLUG,
    roles=frozenset({"admin"}),
    permissions=frozenset(),
)


def get_request_context() -> RequestContext:
    """Get the current request context. Raises if no context is set.

    Use :func:`get_request_context_or_system` for code paths that
    legitimately run outside a request (e.g. event handlers).
    """
    try:
        return _current_context.get()
    except LookupError:
        raise RuntimeError(
            "No request context set. This code path requires an authenticated request. "
            "If running outside a request, use get_request_context_or_system()."
        ) from None


def get_request_context_or_system() -> RequestContext:
    """Get the current request context, falling back to SYSTEM_CONTEXT.

    Only use this for code paths that legitimately run outside a
    request — e.g. event handlers triggered by the simulator.
    """
    try:
        return _current_context.get()
    except LookupError:
        return SYSTEM_CONTEXT


def set_request_context(ctx: RequestContext) -> None:
    """Set the request context for this async task."""
    _current_context.set(ctx)
