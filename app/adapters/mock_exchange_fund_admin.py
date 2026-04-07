"""Mock-exchange fund administrator adapter — fetches admin views via HTTP."""

from __future__ import annotations

from decimal import Decimal

import httpx
import structlog

from app.shared.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()


class MockExchangeFundAdminAdapter:
    """FundAdminAdapter backed by the mock-exchange fund admin service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._circuit = CircuitBreaker(
            "mock-exchange-fund-admin",
            tracked_exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError),
        )

    async def get_positions(self) -> dict[str, Decimal]:
        """Return the administrator's independent position view."""
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            async with self._circuit():
                resp = await client.get("/api/v1/admin/positions")
                resp.raise_for_status()
            data = resp.json()

        return {iid: Decimal(qty) for iid, qty in data.get("positions", {}).items()}

    async def get_cash_balances(self) -> dict[str, Decimal]:
        """Return the administrator's independent cash balance view."""
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            async with self._circuit():
                resp = await client.get("/api/v1/admin/cash")
                resp.raise_for_status()
            data = resp.json()

        return {ccy: Decimal(amt) for ccy, amt in data.get("balances", {}).items()}
