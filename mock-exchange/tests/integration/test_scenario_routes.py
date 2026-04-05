"""Integration tests for /api/v1/scenarios endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestGetState:
    async def test_initial_state(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/scenarios/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "idle"
        assert data["active_scenario"] is None


class TestListPresets:
    async def test_returns_presets(self, test_app: AsyncClient) -> None:
        resp = await test_app.get("/api/v1/scenarios/presets")
        assert resp.status_code == 200
        presets = resp.json()
        assert len(presets) == 6
        names = {p["name"] for p in presets}
        assert "calm" in names
        assert "crash" in names


class TestLoadPreset:
    async def test_load_and_start(self, test_app: AsyncClient) -> None:
        resp = await test_app.post("/api/v1/scenarios/load/calm")
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"
        # Cleanup
        engine = test_app._transport.app.state.scenario_engine  # type: ignore[union-attr]
        engine.stop()

    async def test_load_unknown(self, test_app: AsyncClient) -> None:
        resp = await test_app.post("/api/v1/scenarios/load/nonexistent")
        assert resp.status_code == 404


class TestStopScenario:
    async def test_stop_when_not_running(self, test_app: AsyncClient) -> None:
        resp = await test_app.post("/api/v1/scenarios/stop")
        assert resp.status_code == 400

    async def test_stop_running(self, test_app: AsyncClient) -> None:
        await test_app.post("/api/v1/scenarios/load/calm")
        resp = await test_app.post("/api/v1/scenarios/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"


class TestReset:
    async def test_reset(self, test_app: AsyncClient) -> None:
        resp = await test_app.post("/api/v1/scenarios/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"
