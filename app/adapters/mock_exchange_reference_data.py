"""Mock-exchange reference data adapter — fetches instruments via HTTP."""

from __future__ import annotations

import httpx
import structlog

from app.shared.adapters.reference_data import ExternalInstrument
from app.shared.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()

# Fields accepted by ExternalInstrument — filter incoming JSON to this set
# so the adapter doesn't break when the upstream API adds new fields.
_KNOWN_FIELDS = frozenset(ExternalInstrument.__slots__)


def _parse_instrument(data: dict[str, object]) -> ExternalInstrument:
    """Build an ExternalInstrument, dropping any unknown keys from *data*."""
    filtered = {k: v for k, v in data.items() if k in _KNOWN_FIELDS}
    return ExternalInstrument(**filtered)  # type: ignore[arg-type]


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
            return _parse_instrument(resp.json())

    async def get_all_instruments(self, asset_class: str | None = None) -> list[ExternalInstrument]:
        params: dict[str, str] = {}
        if asset_class:
            params["asset_class"] = asset_class
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            async with self._circuit():
                resp = await client.get("/api/v1/instruments", params=params)
                resp.raise_for_status()
            return [_parse_instrument(item) for item in resp.json()]
