"""Integration tests for /api/v1/prices endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestGetAllPrices:
    async def test_returns_prices(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/prices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 42
        # Each item should have price fields
        item = data[0]
        assert "instrument_id" in item
        assert "bid" in item
        assert "ask" in item
        assert "mid" in item


class TestGetPrice:
    async def test_found(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/prices/AAPL")
        assert resp.status_code == 200
        assert resp.json()["instrument_id"] == "AAPL"

    async def test_not_found(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/prices/FAKE")
        assert resp.status_code == 404
