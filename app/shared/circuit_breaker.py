"""Async circuit breaker for external HTTP calls.

Implements the standard three-state pattern (CLOSED -> OPEN -> HALF_OPEN)
to prevent cascading failures when an external service is unavailable.
"""

from __future__ import annotations

import asyncio
import enum
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is OPEN."""

    def __init__(self, name: str, retry_after: float) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(f"Circuit '{name}' is OPEN — retry after {retry_after:.1f}s")


class _State(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Async circuit breaker for wrapping unreliable external calls.

    Usage::

        cb = CircuitBreaker("mock-exchange-broker")

        # As a context-manager style wrapper:
        async with cb():
            resp = await client.post(...)

        # Or wrap a coroutine directly:
        resp = await cb.call(client.post, "/api/v1/orders", json=body)

    Parameters
    ----------
    name:
        Human-readable name for logging.
    failure_threshold:
        Number of failures within *window_seconds* to trip to OPEN.
    recovery_timeout:
        Seconds to wait in OPEN before transitioning to HALF_OPEN.
    window_seconds:
        Rolling window for counting failures.
    tracked_exceptions:
        Exception types that count as failures.  Exceptions not listed
        here propagate normally without affecting circuit state.
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        window_seconds: float = 60.0,
        tracked_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_seconds = window_seconds
        self.tracked_exceptions = tracked_exceptions

        self._state = _State.CLOSED
        self._failures: list[float] = []  # timestamps of recent failures
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        """Current state as a string."""
        return self._state.value

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: object,
        **kwargs: object,
    ) -> T:
        """Execute *func* through the circuit breaker."""
        await self._before_call()
        try:
            result = await func(*args, **kwargs)
        except BaseException as exc:
            await self._on_failure(exc)
            raise
        else:
            await self._on_success()
            return result

    def __call__(self) -> _CircuitBreakerContext:
        """Return an async context manager that guards the enclosed block."""
        return _CircuitBreakerContext(self)

    # ------------------------------------------------------------------
    # Internal state machine
    # ------------------------------------------------------------------

    async def _before_call(self) -> None:
        async with self._lock:
            if self._state is _State.OPEN:
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self.recovery_timeout:
                    self._transition(_State.HALF_OPEN)
                else:
                    retry_after = self.recovery_timeout - elapsed
                    raise CircuitOpenError(self.name, retry_after)

            # HALF_OPEN: allow the single probe request through (no gate)
            # CLOSED: allow all requests through

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state is _State.HALF_OPEN:
                self._reset()
            # In CLOSED state a success doesn't change anything.

    async def _on_failure(self, exc: BaseException) -> None:
        if not isinstance(exc, self.tracked_exceptions):
            return  # not a tracked failure

        async with self._lock:
            if self._state is _State.HALF_OPEN:
                # Probe failed — back to OPEN
                self._transition(_State.OPEN)
                self._opened_at = time.monotonic()
                return

            if self._state is _State.CLOSED:
                now = time.monotonic()
                cutoff = now - self.window_seconds
                self._failures = [t for t in self._failures if t > cutoff]
                self._failures.append(now)

                if len(self._failures) >= self.failure_threshold:
                    self._transition(_State.OPEN)
                    self._opened_at = now

    def _transition(self, new_state: _State) -> None:
        old = self._state
        self._state = new_state
        logger.warning(
            "circuit_breaker_state_change",
            circuit=self.name,
            from_state=old.value,
            to_state=new_state.value,
        )
        _record_state_metrics(self.name, old, new_state)

    def _reset(self) -> None:
        old = self._state
        self._state = _State.CLOSED
        self._failures.clear()
        logger.info(
            "circuit_breaker_reset",
            circuit=self.name,
        )
        _record_state_metrics(self.name, old, _State.CLOSED)


# ---------------------------------------------------------------------------
# Prometheus metrics integration (best-effort — silent if unavailable)
# ---------------------------------------------------------------------------

_STATE_GAUGE_VALUE: dict[_State, int] = {
    _State.CLOSED: 0,
    _State.HALF_OPEN: 1,
    _State.OPEN: 2,
}


def _record_state_metrics(name: str, old: _State, new: _State) -> None:
    """Emit Prometheus metrics for a state transition. Silent on import error."""
    try:
        # Local import to avoid circular import during metrics module bootstrap
        # and to keep this module importable in environments without the
        # observability stack (tests, scripts).
        from app.shared.observability.metrics import (
            circuit_breaker_state,
            circuit_breaker_state_transitions_total,
        )

        circuit_breaker_state_transitions_total.labels(
            circuit=name, from_state=old.value, to_state=new.value
        ).inc()
        circuit_breaker_state.labels(circuit=name).set(_STATE_GAUGE_VALUE[new])
    except Exception:  # noqa: BLE001 — metrics must never break request path
        pass


class _CircuitBreakerContext:
    """Async context manager returned by ``CircuitBreaker()``."""

    def __init__(self, cb: CircuitBreaker) -> None:
        self._cb = cb

    async def __aenter__(self) -> None:
        await self._cb._before_call()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_val is not None:
            await self._cb._on_failure(exc_val)
        else:
            await self._cb._on_success()
