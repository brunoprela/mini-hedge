"""Shared Temporal client singleton."""

from __future__ import annotations

import asyncio

from temporalio.client import Client

from app.config import get_settings

_client: Client | None = None
_lock = asyncio.Lock()


async def get_temporal_client() -> Client:
    """Get or create the shared Temporal client."""
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client
    async with _lock:
        if _client is None:
            settings = get_settings()
            _client = await Client.connect(f"{settings.temporal_host}:{settings.temporal_port}")
    return _client


async def close_temporal_client() -> None:
    """Close the shared Temporal client during shutdown."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.service_client.close()
        _client = None
