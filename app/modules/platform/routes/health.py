"""Health check endpoints — liveness and readiness probes.

Exposes:

- ``GET /health``       — liveness: always returns 200 while the process is up.
- ``GET /health/ready`` — readiness: parallel checks against DB, Kafka,
  Keycloak, OpenFGA, and Redis.  Returns 503 if any dependency fails.

Each readiness check is a focused async function bounded by a 2-second
timeout.  Checks run concurrently so the overall probe completes in
~2 s worst case rather than (N × 2) s serially.

Response format for ``/health/ready``::

    {
        "status": "ok" | "degraded",
        "checks": {
            "db": "ok" | "down" | "timeout" | "skipped",
            "kafka": "...",
            "keycloak": "...",
            "openfga": "...",
            "redis": "..."
        },
        "circuits": {"keycloak": "CLOSED", "openfga": "CLOSED"}
    }
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = structlog.get_logger()

router = APIRouter(tags=["health"])

# Per-check timeout.  The overall readiness probe returns in ~2 s because
# all checks run in parallel with the same budget.
_CHECK_TIMEOUT_SECS = 2.0


# ---------------------------------------------------------------------------
# Individual checks — each returns "ok" on success, a short status string on
# failure.  Checks never raise; they always translate errors into a status.
# ---------------------------------------------------------------------------


async def check_db(request: Request) -> str:
    """``SELECT 1`` through the app's primary async engine."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return "skipped"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001 — intentionally broad
        logger.warning("health_check_db_failed", error=str(exc))
        return "down"


async def check_kafka(request: Request) -> str:
    """Probe the Kafka producer via the KafkaEventBus.health_check()."""
    kafka_bus = getattr(request.app.state, "kafka_bus", None)
    if kafka_bus is None:
        return "skipped"
    try:
        ok = await kafka_bus.health_check()
        return "ok" if ok else "down"
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_check_kafka_failed", error=str(exc))
        return "down"


async def check_keycloak(request: Request) -> str:
    """Fetch JWKS from the configured Keycloak realm."""
    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is None:
        return "skipped"
    validator = getattr(auth_service, "_jwt_validator", None)
    if validator is None or not validator.keycloak_url:
        return "skipped"
    jwks_url = (
        f"{validator.keycloak_url}/realms/"
        f"{validator.keycloak_realm}/protocol/openid-connect/certs"
    )
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_CHECK_TIMEOUT_SECS, connect=1.0),
        ) as client:
            resp = await client.get(jwks_url)
            if resp.status_code == 200:
                return "ok"
            return "down"
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_check_keycloak_failed", error=str(exc))
        return "down"


async def check_openfga(request: Request) -> str:
    """List stores via the OpenFGA SDK to confirm the service is reachable."""
    fga = getattr(request.app.state, "fga", None)
    if fga is None:
        return "skipped"
    sdk_client = getattr(fga, "_client", None)
    if sdk_client is None:
        return "skipped"
    try:
        await sdk_client.list_stores()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_check_openfga_failed", error=str(exc))
        return "down"


async def check_redis(request: Request) -> str:
    """PING Redis to confirm connectivity."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return "skipped"
    try:
        await redis.ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_check_redis_failed", error=str(exc))
        return "down"


# ---------------------------------------------------------------------------
# Runner — enforces per-check timeout and keeps the response shape stable.
# ---------------------------------------------------------------------------


async def _run_with_timeout(name: str, coro: Any) -> tuple[str, str]:
    """Run *coro* with a 2-second timeout, returning ``(name, status)``."""
    try:
        status = await asyncio.wait_for(coro, timeout=_CHECK_TIMEOUT_SECS)
    except asyncio.TimeoutError:
        status = "timeout"
    except Exception as exc:  # noqa: BLE001 — never leak raw exceptions
        logger.warning("health_check_error", check=name, error=str(exc))
        status = "down"
    return name, status


def _circuit_states(request: Request) -> dict[str, str]:
    """Snapshot the keycloak/openfga circuit breaker states."""
    states: dict[str, str] = {}
    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is not None:
        cb = getattr(auth_service, "_keycloak_circuit", None)
        if cb is not None:
            states["keycloak"] = cb.state
    fga = getattr(request.app.state, "fga", None)
    if fga is not None:
        cb = getattr(fga, "_circuit", None)
        if cb is not None:
            states["openfga"] = cb.state
    return states


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/health")
async def liveness() -> dict[str, str]:
    """Liveness probe — the process is up.  No dependency checks."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Readiness probe — checks all external dependencies in parallel."""
    checks = [
        _run_with_timeout("db", check_db(request)),
        _run_with_timeout("kafka", check_kafka(request)),
        _run_with_timeout("keycloak", check_keycloak(request)),
        _run_with_timeout("openfga", check_openfga(request)),
        _run_with_timeout("redis", check_redis(request)),
    ]
    results = await asyncio.gather(*checks)
    checks_map = dict(results)

    # "skipped" means the dependency isn't configured — treat as OK.
    failed = [name for name, status in checks_map.items() if status not in ("ok", "skipped")]
    overall_status = "ok" if not failed else "degraded"
    http_status = 200 if not failed else 503

    payload: dict[str, Any] = {
        "status": overall_status,
        "checks": checks_map,
    }
    circuits = _circuit_states(request)
    if circuits:
        payload["circuits"] = circuits

    return JSONResponse(status_code=http_status, content=payload)
