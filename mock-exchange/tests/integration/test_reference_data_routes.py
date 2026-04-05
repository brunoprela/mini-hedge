"""Integration tests for /api/v1/instruments endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestListInstruments:
    async def test_returns_all(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/instruments")
        assert resp.status_code == 200
        assert len(resp.json()) == 42

    async def test_filter_by_country(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/instruments", params={"country": "GB"})
        assert resp.status_code == 200
        assert len(resp.json()) == 6

    async def test_filter_by_sector(self, test_app: AsyncClient) -> None:
        resp = await test_app.get(
            "/api/v1/instruments", params={"sector": "Energy"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 5


class TestGetInstrumentDetail:
    async def test_found(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/instruments/AAPL")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

    async def test_not_found(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/instruments/FAKE")
        assert resp.status_code == 404

    async def test_case_insensitive(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/instruments/aapl")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"
