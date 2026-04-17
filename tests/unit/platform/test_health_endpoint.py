"""Unit tests for the /health and /health/ready endpoints.

Exercises the route handlers directly with a Request whose app.state is
populated with mocked dependencies.  Avoids spinning up the full FastAPI
TestClient — the handlers are pure functions of ``request.app.state``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.routes.health import liveness, readiness


def _make_request(**state: object) -> MagicMock:
    """Build a MagicMock Request whose app.state exposes the given attrs."""
    request = MagicMock()
    request.app = MagicMock()
    request.app.state = SimpleNamespace(**state)
    return request


def _make_engine_ok() -> MagicMock:
    """Mock engine whose ``connect()`` context yields a conn that executes SELECT 1."""
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    engine = MagicMock()
    engine.connect = MagicMock(return_value=ctx)
    return engine


def _make_engine_fail() -> MagicMock:
    """Mock engine whose connect() raises on enter."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("db down"))
    ctx.__aexit__ = AsyncMock(return_value=None)
    engine = MagicMock()
    engine.connect = MagicMock(return_value=ctx)
    return engine


class TestLiveness:
    """``GET /health`` — always 200 regardless of dependencies."""

    @pytest.mark.asyncio
    async def test_liveness_always_ok(self) -> None:
        result = await liveness()
        assert result == {"status": "ok"}


class TestReadinessAllOk:
    """All dependencies healthy — returns 200 ok."""

    @pytest.mark.asyncio
    async def test_all_deps_healthy(self) -> None:
        kafka_bus = MagicMock()
        kafka_bus.health_check = AsyncMock(return_value=True)
        redis = MagicMock()
        redis.ping = AsyncMock(return_value=True)

        request = _make_request(
            engine=_make_engine_ok(),
            kafka_bus=kafka_bus,
            redis=redis,
            # auth_service / fga absent → those checks resolve as "skipped"
        )

        response = await readiness(request)
        assert response.status_code == 200
        body = _json(response)
        assert body["status"] == "ok"
        assert body["checks"]["db"] == "ok"
        assert body["checks"]["kafka"] == "ok"
        assert body["checks"]["redis"] == "ok"
        # Unconfigured dependencies are reported as skipped.
        assert body["checks"]["keycloak"] == "skipped"
        assert body["checks"]["openfga"] == "skipped"

    @pytest.mark.asyncio
    async def test_skipped_deps_do_not_degrade_status(self) -> None:
        """A bare app (no redis, no kafka, no fga, no auth_service) still returns ok."""
        request = _make_request(engine=_make_engine_ok())

        response = await readiness(request)
        assert response.status_code == 200
        body = _json(response)
        assert body["status"] == "ok"
        for name in ("db", "kafka", "keycloak", "openfga", "redis"):
            assert body["checks"][name] in ("ok", "skipped")


class TestReadinessFailures:
    """Any failed dependency flips the overall status to degraded (503)."""

    @pytest.mark.asyncio
    async def test_db_failure_is_degraded(self) -> None:
        kafka_bus = MagicMock()
        kafka_bus.health_check = AsyncMock(return_value=True)

        request = _make_request(engine=_make_engine_fail(), kafka_bus=kafka_bus)
        response = await readiness(request)

        assert response.status_code == 503
        body = _json(response)
        assert body["status"] == "degraded"
        assert body["checks"]["db"] == "down"
        assert body["checks"]["kafka"] == "ok"

    @pytest.mark.asyncio
    async def test_redis_ping_failure_is_degraded(self) -> None:
        kafka_bus = MagicMock()
        kafka_bus.health_check = AsyncMock(return_value=True)
        redis = MagicMock()
        redis.ping = AsyncMock(side_effect=ConnectionError("redis down"))

        request = _make_request(
            engine=_make_engine_ok(), kafka_bus=kafka_bus, redis=redis,
        )
        response = await readiness(request)

        assert response.status_code == 503
        body = _json(response)
        assert body["checks"]["redis"] == "down"
        assert body["checks"]["db"] == "ok"

    @pytest.mark.asyncio
    async def test_kafka_reports_unhealthy(self) -> None:
        kafka_bus = MagicMock()
        kafka_bus.health_check = AsyncMock(return_value=False)

        request = _make_request(engine=_make_engine_ok(), kafka_bus=kafka_bus)
        response = await readiness(request)

        assert response.status_code == 503
        body = _json(response)
        assert body["checks"]["kafka"] == "down"

    @pytest.mark.asyncio
    async def test_sensitive_info_is_not_leaked(self) -> None:
        """Down statuses are short strings — no stack traces, no secrets."""
        kafka_bus = MagicMock()
        kafka_bus.health_check = AsyncMock(
            side_effect=RuntimeError("DATABASE_URL=postgres://user:pw@host/db")
        )

        request = _make_request(engine=_make_engine_ok(), kafka_bus=kafka_bus)
        response = await readiness(request)

        body = _json(response)
        # The check must never include the raw exception text — only a
        # short status.
        for status in body["checks"].values():
            assert "postgres://" not in status
            assert "DATABASE_URL" not in status
            assert status in ("ok", "skipped", "down", "timeout")


class TestReadinessCircuitState:
    """The /health/ready payload surfaces keycloak/openfga circuit state."""

    @pytest.mark.asyncio
    async def test_includes_circuit_states_when_available(self) -> None:
        keycloak_cb = MagicMock()
        keycloak_cb.state = "HALF_OPEN"
        auth_service = MagicMock()
        auth_service._keycloak_circuit = keycloak_cb
        # Simulate "not configured" for the keycloak JWKS fetch itself by
        # leaving _jwt_validator.keycloak_url empty — the check returns
        # "skipped" but the circuit state still shows up.
        auth_service._jwt_validator = MagicMock(keycloak_url="")

        openfga_cb = MagicMock()
        openfga_cb.state = "CLOSED"
        fga = MagicMock()
        fga._circuit = openfga_cb
        fga._client = None  # forces check_openfga → "skipped"

        request = _make_request(
            engine=_make_engine_ok(),
            auth_service=auth_service,
            fga=fga,
        )
        response = await readiness(request)

        body = _json(response)
        assert body["circuits"] == {"keycloak": "HALF_OPEN", "openfga": "CLOSED"}


class TestReadinessTimeout:
    """A check that hangs beyond 2 seconds is reported as ``timeout``."""

    @pytest.mark.asyncio
    async def test_slow_check_times_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Replace the per-check timeout with something tight so the test
        # doesn't block for 2 s.
        monkeypatch.setattr(
            "app.modules.platform.routes.health._CHECK_TIMEOUT_SECS",
            0.05,
        )

        class _SlowBus:
            async def health_check(self) -> bool:
                await asyncio.sleep(1.0)
                return True

        request = _make_request(engine=_make_engine_ok(), kafka_bus=_SlowBus())
        response = await readiness(request)

        body = _json(response)
        assert body["checks"]["kafka"] == "timeout"
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _json(response: object) -> dict[str, object]:
    """Decode the JSONResponse body."""
    import json as _json_mod

    body = getattr(response, "body", None)
    assert body is not None
    return _json_mod.loads(body.decode())
