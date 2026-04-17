"""Shared Temporal client factory.

Exposes a class-based ``TemporalClientFactory`` with explicit lifecycle
methods (``connect`` / ``close``) so the client can be wired onto
``app.state`` and injected into callers, matching the pattern used by
``AuthService``, ``FGAClient`` and other shared services.

The legacy module-level ``get_temporal_client`` / ``close_temporal_client``
helpers remain as thin wrappers around a process-wide default factory to
preserve backwards compatibility with scripts that run outside the
FastAPI lifecycle (e.g. the standalone Temporal worker process).
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client

from app.config import get_settings


class TemporalClientFactory:
    """Lifecycle-managed Temporal client suitable for DI via ``app.state``.

    Usage::

        factory = TemporalClientFactory(host="localhost", port=7233)
        await factory.connect()
        client = factory.client
        ...
        await factory.close()
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    @property
    def client(self) -> Client:
        """Return the connected Temporal client.

        Raises ``RuntimeError`` if ``connect`` has not been awaited yet.
        """
        if self._client is None:
            raise RuntimeError(
                "TemporalClientFactory.connect() must be awaited before accessing .client"
            )
        return self._client

    async def connect(self) -> Client:
        """Establish the Temporal connection if not already connected."""
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                self._client = await Client.connect(f"{self._host}:{self._port}")
        return self._client

    async def close(self) -> None:
        """Close the Temporal connection if it was opened."""
        if self._client is not None:
            await self._client.service_client.close()
            self._client = None

    @classmethod
    def from_settings(cls) -> TemporalClientFactory:
        """Build a factory using ``app.config.get_settings()``."""
        settings = get_settings()
        return cls(host=settings.temporal_host, port=settings.temporal_port)


# ---------------------------------------------------------------------------
# Back-compat module-level helpers — used by the standalone worker process
# and any callers that run outside the FastAPI app lifecycle.
# ---------------------------------------------------------------------------

_default_factory: TemporalClientFactory | None = None
_default_lock = asyncio.Lock()


async def get_temporal_client() -> Client:
    """Return a process-wide Temporal client (legacy helper).

    Prefer accessing ``app.state.temporal_client_factory`` inside request
    handlers / wiring code so the factory can be mocked in tests.
    """
    global _default_factory  # noqa: PLW0603
    if _default_factory is not None and _default_factory._client is not None:
        return _default_factory._client
    async with _default_lock:
        if _default_factory is None:
            _default_factory = TemporalClientFactory.from_settings()
        return await _default_factory.connect()


async def close_temporal_client() -> None:
    """Close the process-wide Temporal client, if open (legacy helper)."""
    global _default_factory  # noqa: PLW0603
    if _default_factory is not None:
        await _default_factory.close()
        _default_factory = None
