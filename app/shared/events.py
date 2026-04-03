"""In-process event bus — will be replaced by Kafka adapter in a later phase."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger()


class BaseEvent(BaseModel):
    """Envelope for all domain events."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    event_version: int = 1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any]
    actor_id: str | None = None
    actor_type: str | None = None
    fund_slug: str | None = None


EventHandler = Callable[[BaseEvent], Awaitable[None]]


class EventBus(Protocol):
    """Protocol for event publishing/subscribing.

    In-process implementation below; Kafka implementation swaps in later.
    """

    async def publish(self, topic: str, event: BaseEvent) -> None: ...

    def subscribe(self, topic: str, handler: EventHandler) -> None: ...


class InProcessEventBus:
    """Simple async event bus backed by handler lists.

    Handlers run concurrently via asyncio.gather. Each handler is isolated:
    a failure in one handler does not cancel or prevent other handlers from
    completing (return_exceptions=True).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    async def publish(self, topic: str, event: BaseEvent) -> None:
        handlers = self._handlers.get(topic, [])
        if not handlers:
            return
        results = await asyncio.gather(*(h(event) for h in handlers), return_exceptions=True)
        errors: list[Exception] = []
        for handler, result in zip(handlers, results, strict=True):
            if isinstance(result, Exception):
                logger.error(
                    "event_handler_failed",
                    topic=topic,
                    handler=getattr(handler, "__qualname__", str(handler)),
                    event_id=event.event_id,
                    error=str(result),
                )
                errors.append(result)
        if errors:
            raise ExceptionGroup("event handler failures", errors)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._handlers[topic].append(handler)
