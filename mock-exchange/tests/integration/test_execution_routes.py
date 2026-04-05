"""Integration tests for /api/v1/orders endpoints."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.factories import make_submit_order_payload

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestSubmitOrder:
    async def test_submit_acknowledged(self, test_app: AsyncClient) -> None:
        resp = await test_app.post(
            "/api/v1/orders", json=make_submit_order_payload(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert data["exchange_order_id"]
        assert data["client_order_id"] == "test-001"

    async def test_submit_rejected(self, test_app: AsyncClient) -> None:
        # Set reject_rate to 1.0 on the engine
        test_app._transport.app.state.execution_engine.update_config(  # type: ignore[union-attr]
            reject_rate=1.0,
        )
        resp = await test_app.post(
            "/api/v1/orders", json=make_submit_order_payload(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


class TestGetOrder:
    async def test_found(self, test_app: AsyncClient) -> None:
        # Submit first
        resp = await test_app.post(
            "/api/v1/orders", json=make_submit_order_payload(),
        )
        eid = resp.json()["exchange_order_id"]
        resp = await test_app.get(f"/api/v1/orders/{eid}")
        assert resp.status_code == 200
        assert resp.json()["exchange_order_id"] == eid

    async def test_not_found(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/orders/nonexistent")
        assert resp.status_code == 404


class TestCancelOrder:
    async def test_cancel_success(self, test_app: AsyncClient) -> None:
        resp = await test_app.post(
            "/api/v1/orders", json=make_submit_order_payload(),
        )
        eid = resp.json()["exchange_order_id"]
        resp = await test_app.delete(f"/api/v1/orders/{eid}")
        assert resp.status_code == 200
        assert resp.json()["cancelled"] is True

    async def test_cancel_filled_fails(self, test_app: AsyncClient) -> None:
        test_app._transport.app.state.execution_engine.update_config(  # type: ignore[union-attr]
            fill_delay_ms=0,
        )
        resp = await test_app.post(
            "/api/v1/orders", json=make_submit_order_payload(),
        )
        eid = resp.json()["exchange_order_id"]
        await asyncio.sleep(0.05)
        resp = await test_app.delete(f"/api/v1/orders/{eid}")
        assert resp.status_code == 400
