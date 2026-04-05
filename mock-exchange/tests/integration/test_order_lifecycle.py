"""End-to-end order lifecycle integration tests."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.factories import make_submit_order_payload

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestOrderLifecycle:
    async def test_submit_fill_query(self, test_app: AsyncClient) -> None:
        """Submit → fill → query: full lifecycle."""
        test_app._transport.app.state.execution_engine.update_config(  # type: ignore[union-attr]
            fill_delay_ms=0,
        )
        # Submit
        resp = await test_app.post(
            "/api/v1/orders",
            json=make_submit_order_payload(limit_price="150.00"),
        )
        assert resp.status_code == 200
        eid = resp.json()["exchange_order_id"]

        # Wait for async fill
        await asyncio.sleep(0.05)

        # Query
        resp = await test_app.get(f"/api/v1/orders/{eid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "filled"
        assert data["filled_quantity"] == "100"
        assert len(data["fills"]) == 1
        assert data["avg_fill_price"] is not None

    async def test_submit_cancel(self, test_app: AsyncClient) -> None:
        """Submit → cancel lifecycle."""
        resp = await test_app.post(
            "/api/v1/orders", json=make_submit_order_payload(),
        )
        eid = resp.json()["exchange_order_id"]

        resp = await test_app.delete(f"/api/v1/orders/{eid}")
        assert resp.status_code == 200

        resp = await test_app.get(f"/api/v1/orders/{eid}")
        assert resp.json()["status"] == "cancelled"


class TestHealthEndpoint:
    async def test_health(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "mock-exchange"}
