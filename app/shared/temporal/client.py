"""Shared Temporal client singleton."""

from __future__ import annotations

from temporalio.client import Client

from app.config import get_settings

_client: Client | None = None


async def get_temporal_client() -> Client:
    """Get or create the shared Temporal client."""
    global _client  # noqa: PLW0603
    if _client is None:
        settings = get_settings()
        _client = await Client.connect(f"{settings.temporal_host}:{settings.temporal_port}")
    return _client
