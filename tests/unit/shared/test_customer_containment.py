"""Unit tests for customer containment check in require_permission()."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.shared.auth.permissions import Permission, require_permission
from app.shared.auth.request_context import ActorType, RequestContext, set_request_context


def _make_app():
    """Create a minimal FastAPI app with a protected route."""
    app = FastAPI()

    @app.get("/test", dependencies=[require_permission(Permission.POSITIONS_READ)])
    async def test_route():
        return {"ok": True}

    return app


def _set_context(ctx: RequestContext) -> None:
    """Set the request context for the current test."""
    set_request_context(ctx)


class TestCustomerContainment:
    def test_same_customer_allowed(self) -> None:
        app = _make_app()
        client = TestClient(app)

        ctx = RequestContext(
            actor_id="user-1",
            actor_type=ActorType.USER,
            customer_id="cust-A",
            home_customer_id="cust-A",
            permissions=frozenset({"positions:read"}),
        )

        with patch("app.shared.auth.permissions.get_request_context", return_value=ctx):
            resp = client.get("/test")
        assert resp.status_code == 200

    def test_different_customer_blocked(self) -> None:
        app = _make_app()
        client = TestClient(app)

        ctx = RequestContext(
            actor_id="user-1",
            actor_type=ActorType.USER,
            customer_id="cust-B",  # resource belongs to cust-B
            home_customer_id="cust-A",  # actor is from cust-A
            permissions=frozenset({"positions:read"}),
        )

        with patch("app.shared.auth.permissions.get_request_context", return_value=ctx):
            resp = client.get("/test")
        assert resp.status_code == 403
        assert "containment" in resp.json()["detail"].lower()

    def test_delegated_user_with_matching_acting_as(self) -> None:
        app = _make_app()
        client = TestClient(app)

        ctx = RequestContext(
            actor_id="admin-1",
            actor_type=ActorType.USER,
            customer_id="cust-B",  # resource is cust-B
            home_customer_id="cust-A",  # admin's home is cust-A
            acting_as_customer_id="cust-B",  # delegated to act on cust-B
            permissions=frozenset({"positions:read"}),
        )

        with patch("app.shared.auth.permissions.get_request_context", return_value=ctx):
            resp = client.get("/test")
        assert resp.status_code == 200

    def test_delegated_user_wrong_customer(self) -> None:
        app = _make_app()
        client = TestClient(app)

        ctx = RequestContext(
            actor_id="admin-1",
            actor_type=ActorType.USER,
            customer_id="cust-C",  # resource is cust-C
            home_customer_id="cust-A",
            acting_as_customer_id="cust-B",  # delegated to cust-B, not cust-C
            permissions=frozenset({"positions:read"}),
        )

        with patch("app.shared.auth.permissions.get_request_context", return_value=ctx):
            resp = client.get("/test")
        assert resp.status_code == 403

    def test_platform_operator_bypasses_containment(self) -> None:
        app = _make_app()
        client = TestClient(app)

        ctx = RequestContext(
            actor_id="ops-1",
            actor_type=ActorType.OPERATOR,
            customer_id="cust-A",
            home_customer_id=None,
            permissions=frozenset({"positions:read"}),
        )

        with patch("app.shared.auth.permissions.get_request_context", return_value=ctx):
            resp = client.get("/test")
        assert resp.status_code == 200

    def test_no_customer_id_passes_containment(self) -> None:
        """When customer_id is None (e.g., system-level routes), containment is skipped."""
        app = _make_app()
        client = TestClient(app)

        ctx = RequestContext(
            actor_id="user-1",
            actor_type=ActorType.USER,
            customer_id=None,
            home_customer_id="cust-A",
            permissions=frozenset({"positions:read"}),
        )

        with patch("app.shared.auth.permissions.get_request_context", return_value=ctx):
            resp = client.get("/test")
        assert resp.status_code == 200

    def test_missing_permission_still_403(self) -> None:
        """Even with matching customer, missing perms still block."""
        app = _make_app()
        client = TestClient(app)

        ctx = RequestContext(
            actor_id="user-1",
            actor_type=ActorType.USER,
            customer_id="cust-A",
            home_customer_id="cust-A",
            permissions=frozenset(),  # no permissions
        )

        with patch("app.shared.auth.permissions.get_request_context", return_value=ctx):
            resp = client.get("/test")
        assert resp.status_code == 403
        assert "Missing permissions" in resp.json()["detail"]
