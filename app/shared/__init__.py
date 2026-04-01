"""Shared kernel — minimal types and infrastructure used across all modules."""

from app.shared.database import build_engine
from app.shared.errors import DomainError, NotFoundError, ValidationError
from app.shared.events import BaseEvent, EventBus, InProcessEventBus
from app.shared.types import InstrumentId, Money

__all__ = [
    "BaseEvent",
    "DomainError",
    "EventBus",
    "InProcessEventBus",
    "InstrumentId",
    "Money",
    "NotFoundError",
    "ValidationError",
    "build_engine",
]
