"""Async wrapper around the immudb-py SDK.

immudb-py is synchronous, so all calls are dispatched to a thread pool
via ``asyncio.to_thread()``.  The client writes audit events as
verified-set key/value pairs.  Each event is keyed by ``event_id`` and
the value is the canonical JSON payload — the same data that the
AuditBridge writes to PostgreSQL.

immudb's storage engine (Merkle tree) guarantees that once written,
a record cannot be modified without detection.  Clients can request
a cryptographic inclusion proof for any key at any time.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

logger = structlog.get_logger()


class ImmudbClient:
    """Async-safe wrapper around the immudb-py synchronous client."""

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 3322,
        username: str = "immudb",
        password: str = "immudb",
        database: str = "defaultdb",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._database = database
        self._client: Any | None = None

    async def connect(self) -> None:
        """Establish connection and authenticate with immudb."""
        from immudb import ImmudbClient as _SyncClient

        def _connect() -> Any:
            client = _SyncClient(f"{self._host}:{self._port}")
            client.login(self._username, self._password, self._database)
            return client

        self._client = await asyncio.to_thread(_connect)
        logger.info(
            "immudb_connected",
            host=self._host,
            port=self._port,
            database=self._database,
        )

    async def verified_set(self, key: str, value: dict[str, Any]) -> None:
        """Write a key/value pair with cryptographic verification.

        Uses ``verifiedSet`` which returns an inclusion proof from the
        server's Merkle tree — guaranteeing the write was persisted
        immutably.
        """
        assert self._client is not None, "Call connect() first"

        encoded_key = key.encode("utf-8")
        encoded_value = json.dumps(value, default=str, sort_keys=True).encode("utf-8")

        await asyncio.to_thread(self._client.verifiedSet, encoded_key, encoded_value)

    async def verified_get(self, key: str) -> dict[str, Any] | None:
        """Read a key with cryptographic inclusion proof.

        Returns ``None`` if the key does not exist.
        """
        assert self._client is not None, "Call connect() first"

        try:
            result = await asyncio.to_thread(self._client.verifiedGet, key.encode("utf-8"))
            return json.loads(result.value.decode("utf-8"))  # type: ignore[union-attr]
        except Exception:
            return None

    async def close(self) -> None:
        """Close the immudb connection."""
        if self._client is not None:
            try:
                await asyncio.to_thread(self._client.logout)
            except Exception:
                logger.debug("immudb_logout_ignored")
            self._client = None
            logger.info("immudb_disconnected")
