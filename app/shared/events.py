"""In-process event bus — will be replaced by Kafka adapter in a later phase."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class BaseEvent(BaseModel):
    """Envelope for all domain events."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any]


EventHandler = Any  # Callable[[BaseEvent], Awaitable[None]] — relaxed for Protocol compat


class EventBus(Protocol):
    """Protocol for event publishing/subscribing.

    In-process implementation below; Kafka implementation swaps in later.
    """

    async def publish(self, topic: str, event: BaseEvent) -> None: ...

    def subscribe(self, topic: str, handler: EventHandler) -> None: ...


class InProcessEventBus:
    """Simple async event bus backed by handler lists.

    Handlers run concurrently via asyncio.gather for each published event.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    async def publish(self, topic: str, event: BaseEvent) -> None:
        handlers = self._handlers.get(topic, [])
        if handlers:
            await asyncio.gather(*(h(event) for h in handlers))

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._handlers[topic].append(handler)
