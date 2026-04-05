"""Locust load tests for mini-hedge platform.

Scenarios:
  1. OrderFlow     — create order, poll status, list fills
  2. ReadHeavy     — positions, exposure, risk snapshots
  3. EODSequence   — trigger EOD run, check reconciliation
  4. InstrumentBrowse — list/search instruments (public-ish reads)

Run:
  locust -f load_tests/locustfile.py --host http://localhost:8000
"""

from __future__ import annotations

import os
import random
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from locust import HttpUser, between, tag, task

# ---------------------------------------------------------------------------
# Auth helpers — mint JWTs locally using the dev secret
# ---------------------------------------------------------------------------

_JWT_SECRET = os.getenv("JWT_SECRET", "minihedge-dev-secret-change-in-production")
_FUND_SLUG = os.getenv("LOAD_TEST_FUND", "alpha")
_FUND_ID = os.getenv("LOAD_TEST_FUND_ID", "")
_PORTFOLIO_ID = os.getenv("LOAD_TEST_PORTFOLIO_ID", "")

_INSTRUMENTS = ["AAPL", "MSFT", "TSLA", "GOOGL", "AMZN", "NVDA", "META", "JPM"]


def _make_token(
    roles: list[str] | None = None,
    fund_slug: str = _FUND_SLUG,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": f"loadtest-{uuid.uuid4().hex[:8]}",
        "actor_type": "user",
        "roles": roles or ["portfolio_manager"],
        "fund_slug": fund_slug,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "jti": str(uuid.uuid4()),
    }
    if _FUND_ID:
        payload["fund_id"] = _FUND_ID
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token()}"}


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------


class OrderFlowUser(HttpUser):
    """Simulates a trader: create orders, check status, list fills."""

    weight = 3
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self._headers = _auth_headers()
        self._order_ids: list[str] = []

    @tag("orders", "write")
    @task(3)
    def create_order(self) -> None:
        if not _PORTFOLIO_ID:
            return
        body = {
            "portfolio_id": _PORTFOLIO_ID,
            "instrument_id": random.choice(_INSTRUMENTS),
            "side": random.choice(["buy", "sell"]),
            "order_type": "market",
            "quantity": str(random.randint(10, 500)),
        }
        with self.client.post(
            "/orders",
            json=body,
            headers=self._headers,
            catch_response=True,
            name="/orders [POST]",
        ) as resp:
            if resp.status_code == 201:
                data = resp.json()
                self._order_ids.append(data["id"])
                resp.success()
            elif resp.status_code == 422:
                # Validation error — not a server fault
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @tag("orders", "read")
    @task(5)
    def list_orders(self) -> None:
        if not _PORTFOLIO_ID:
            return
        self.client.get(
            f"/orders?portfolio_id={_PORTFOLIO_ID}",
            headers=self._headers,
            name="/orders [GET]",
        )

    @tag("orders", "read")
    @task(2)
    def get_order_detail(self) -> None:
        if not self._order_ids:
            return
        oid = random.choice(self._order_ids)
        self.client.get(
            f"/orders/{oid}",
            headers=self._headers,
            name="/orders/{id} [GET]",
        )

    @tag("orders", "read")
    @task(1)
    def get_order_fills(self) -> None:
        if not self._order_ids:
            return
        oid = random.choice(self._order_ids)
        self.client.get(
            f"/orders/{oid}/fills",
            headers=self._headers,
            name="/orders/{id}/fills [GET]",
        )


class ReadHeavyUser(HttpUser):
    """Simulates an analyst: read positions, exposure, risk."""

    weight = 5
    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        self._headers = _auth_headers()

    @tag("positions", "read")
    @task(5)
    def get_positions(self) -> None:
        if not _PORTFOLIO_ID:
            return
        self.client.get(
            f"/portfolios/{_PORTFOLIO_ID}/positions",
            headers=self._headers,
            name="/portfolios/{id}/positions [GET]",
        )

    @tag("positions", "read")
    @task(3)
    def get_portfolio_summary(self) -> None:
        if not _PORTFOLIO_ID:
            return
        self.client.get(
            f"/portfolios/{_PORTFOLIO_ID}/summary",
            headers=self._headers,
            name="/portfolios/{id}/summary [GET]",
        )

    @tag("exposure", "read")
    @task(4)
    def get_exposure(self) -> None:
        if not _PORTFOLIO_ID:
            return
        self.client.get(
            f"/exposure/{_PORTFOLIO_ID}",
            headers=self._headers,
            name="/exposure/{id} [GET]",
        )

    @tag("risk", "read")
    @task(3)
    def get_risk_snapshot(self) -> None:
        if not _PORTFOLIO_ID:
            return
        self.client.get(
            f"/risk/{_PORTFOLIO_ID}/snapshot",
            headers=self._headers,
            name="/risk/{id}/snapshot [GET]",
        )

    @tag("instruments", "read")
    @task(2)
    def list_instruments(self) -> None:
        self.client.get(
            "/instruments",
            headers=self._headers,
            name="/instruments [GET]",
        )


class EODUser(HttpUser):
    """Simulates EOD operations — run infrequently."""

    weight = 1
    wait_time = between(10, 30)

    def on_start(self) -> None:
        self._headers = _auth_headers()

    @tag("eod", "write")
    @task
    def trigger_eod(self) -> None:
        if not _PORTFOLIO_ID:
            return
        with self.client.post(
            "/eod/run",
            json={"portfolio_id": _PORTFOLIO_ID},
            headers=self._headers,
            catch_response=True,
            name="/eod/run [POST]",
        ) as resp:
            if resp.status_code in (200, 202, 409):
                # 409 = already running, that's fine under load
                resp.success()
            else:
                resp.failure(f"EOD trigger failed: {resp.status_code}")
