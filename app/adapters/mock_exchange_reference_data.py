"""Mock-exchange reference data adapter — fetches instruments via HTTP."""

from __future__ import annotations

import httpx
import structlog

from app.shared.adapters import ExternalInstrument
from app.shared.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()


class MockExchangeReferenceDataAdapter:
    """ReferenceDataAdapter backed by the mock-exchange service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._circuit = CircuitBreaker(
            "mock-exchange-reference-data",
            tracked_exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError),
        )

    async def get_instrument(self, ticker: str) -> ExternalInstrument | None:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            async with self._circuit():
                resp = await client.get(f"/api/v1/instruments/{ticker}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
            data = resp.json()
            return ExternalInstrument(**data)

    async def get_all_instruments(self, asset_class: str | None = None) -> list[ExternalInstrument]:
        params: dict[str, str] = {}
        if asset_class:
            params["asset_class"] = asset_class
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            async with self._circuit():
                resp = await client.get("/api/v1/instruments", params=params)
                resp.raise_for_status()
            return [ExternalInstrument(**item) for item in resp.json()]
