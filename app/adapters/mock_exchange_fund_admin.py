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
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(10.0, connect=2.0),
        ) as client:
            async with self._circuit():
                resp = await client.get("/api/v1/admin/positions")
                resp.raise_for_status()
            data = resp.json()

        return {iid: Decimal(qty) for iid, qty in data.get("positions", {}).items()}

    async def get_cash_balances(self) -> dict[str, Decimal]:
        """Return the administrator's independent cash balance view."""
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(10.0, connect=2.0),
        ) as client:
            async with self._circuit():
                resp = await client.get("/api/v1/admin/cash")
                resp.raise_for_status()
            data = resp.json()

        return {ccy: Decimal(amt) for ccy, amt in data.get("balances", {}).items()}

    async def register_subscription(
        self, request_id: str, investor_id: str, amount: Decimal
    ) -> str:
        """Register a subscription and return a wire reference."""
        async with (
            httpx.AsyncClient(base_url=self._base_url, timeout=httpx.Timeout(10.0, connect=2.0)) as client,
            self._circuit(),
        ):
            resp = await client.post(
                "/api/v1/admin/subscriptions",
                json={
                    "request_id": request_id,
                    "investor_id": investor_id,
                    "amount": str(amount),
                },
            )
            resp.raise_for_status()
        return resp.json()["wire_reference"]

    async def confirm_wire_receipt(self, wire_reference: str) -> bool:
        """Confirm bank wire receipt."""
        async with (
            httpx.AsyncClient(base_url=self._base_url, timeout=httpx.Timeout(10.0, connect=2.0)) as client,
            self._circuit(),
        ):
            resp = await client.post(
                "/api/v1/admin/subscriptions/_/confirm-wire",
                json={"wire_reference": wire_reference},
            )
        return resp.status_code == 200

    async def register_redemption(self, request_id: str, investor_id: str, amount: Decimal) -> None:
        """Register a pending redemption payment."""
        async with (
            httpx.AsyncClient(base_url=self._base_url, timeout=httpx.Timeout(10.0, connect=2.0)) as client,
            self._circuit(),
        ):
            resp = await client.post(
                "/api/v1/admin/redemptions",
                json={
                    "request_id": request_id,
                    "investor_id": investor_id,
                    "amount": str(amount),
                },
            )
            resp.raise_for_status()

    async def send_redemption_payment(self, request_id: str) -> str | None:
        """Send a wire for a redemption. Returns payment reference."""
        async with (
            httpx.AsyncClient(base_url=self._base_url, timeout=httpx.Timeout(10.0, connect=2.0)) as client,
            self._circuit(),
        ):
            resp = await client.post(
                f"/api/v1/admin/redemptions/{request_id}/send-payment",
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        return resp.json()["payment_reference"]
