"""Shared realtime infrastructure — SSE streaming via Redis pub/sub."""

from app.shared.realtime.routes import router

__all__ = ["router"]
