"""Broker registry — manages multiple BrokerAdapter instances.

When only one broker is registered (backward compat with single-broker mode),
all routing decisions are trivial. Multi-broker mode enables smart order
routing via the RoutingEngine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.adapters import BrokerAdapter


class BrokerRegistry:
    """Manages named BrokerAdapter instances."""

    def __init__(self) -> None:
        self._brokers: dict[str, BrokerAdapter] = {}
        self._default_broker_id: str | None = None
        self._fill_consumers_started: set[str] = set()

    def register(
        self,
        broker_id: str,
        adapter: BrokerAdapter,
        *,
        default: bool = False,
    ) -> None:
        """Register a broker adapter with an ID."""
        self._brokers[broker_id] = adapter
        if default or self._default_broker_id is None:
            self._default_broker_id = broker_id

    def get(self, broker_id: str) -> BrokerAdapter:
        """Get a broker by ID. Raises KeyError if not found."""
        if broker_id not in self._brokers:
            msg = f"Broker '{broker_id}' not registered"
            raise KeyError(msg)
        return self._brokers[broker_id]

    def get_default(self) -> BrokerAdapter:
        """Get the default broker."""
        if self._default_broker_id is None:
            msg = "No brokers registered"
            raise RuntimeError(msg)
        return self._brokers[self._default_broker_id]

    @property
    def default_broker_id(self) -> str | None:
        return self._default_broker_id

    def list_broker_ids(self) -> list[str]:
        return list(self._brokers.keys())

    def has_fill_consumer(self, broker_id: str) -> bool:
        """Check if a fill consumer has already been started for this broker."""
        return broker_id in self._fill_consumers_started

    def mark_fill_consumer(self, broker_id: str) -> None:
        """Mark that a fill consumer has been started for this broker."""
        self._fill_consumers_started.add(broker_id)

    @property
    def is_single_broker(self) -> bool:
        return len(self._brokers) <= 1
