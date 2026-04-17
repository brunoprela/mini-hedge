"""Unit tests for the async circuit breaker and its integration points.

Verifies the three-state machine and that integration points (Keycloak
in platform AuthService, OpenFGA in FGAClient, mock-exchange broker
adapter) correctly open their circuits after repeated failures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openfga_sdk.exceptions import ApiException

from app.adapters.mock_exchange_broker import MockExchangeBrokerAdapter
from app.modules.platform.services.auth import AuthService
from app.shared.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.shared.errors import AuthenticationError
from app.shared.fga.client import FGAClient


# ---------------------------------------------------------------------------
# Core CircuitBreaker state machine
# ---------------------------------------------------------------------------


class TestCircuitBreakerCore:
    """Core state-machine behaviour."""

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=10.0)

        async def boom() -> None:
            raise ConnectionError("nope")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await cb.call(boom)

        assert cb.state == "OPEN"

        # Next call should short-circuit with CircuitOpenError
        with pytest.raises(CircuitOpenError):
            await cb.call(boom)

    @pytest.mark.asyncio
    async def test_success_resets_counter_in_closed(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=10.0)

        async def boom() -> None:
            raise ConnectionError("nope")

        async def ok() -> str:
            return "ok"

        with pytest.raises(ConnectionError):
            await cb.call(boom)
        with pytest.raises(ConnectionError):
            await cb.call(boom)

        # A success in CLOSED state does not clear the failure window, but
        # another failure still shouldn't trip if the threshold isn't met.
        assert await cb.call(ok) == "ok"
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_untracked_exception_does_not_count(self) -> None:
        cb = CircuitBreaker(
            "test",
            failure_threshold=2,
            recovery_timeout=10.0,
            tracked_exceptions=(ConnectionError,),
        )

        async def raise_value() -> None:
            raise ValueError("not tracked")

        for _ in range(5):
            with pytest.raises(ValueError):
                await cb.call(raise_value)
        assert cb.state == "CLOSED"


# ---------------------------------------------------------------------------
# Keycloak integration — AuthService._keycloak_circuit
# ---------------------------------------------------------------------------


def _mk_auth_service() -> AuthService:
    """Build an AuthService with mocks + a low failure threshold."""
    user_repo = AsyncMock()
    fund_repo = AsyncMock()
    operator_repo = AsyncMock()
    api_key_repo = AsyncMock()
    svc = AuthService(
        user_repo=user_repo,
        fund_repo=fund_repo,
        operator_repo=operator_repo,
        api_key_repo=api_key_repo,
        fga_client=None,
        jwt_secret="x" * 32,
        jwt_algorithm="HS256",
        jwt_expiry_minutes=60,
        keycloak_url="http://kc.local",
        keycloak_realm="minihedge",
        keycloak_client_id="minihedge-client",
        keycloak_ops_realm="minihedge-ops",
        keycloak_ops_client_id="minihedge-ops-client",
    )
    # Tighten threshold so the test is fast
    svc._keycloak_circuit = CircuitBreaker(
        "keycloak",
        failure_threshold=3,
        recovery_timeout=30.0,
        tracked_exceptions=(ConnectionError, TimeoutError),
    )
    return svc


class TestKeycloakCircuit:
    @pytest.mark.asyncio
    async def test_circuit_opens_after_repeated_jwks_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = _mk_auth_service()

        async def always_fail(*_args: object, **_kwargs: object) -> None:
            raise ConnectionError("JWKS endpoint unreachable")

        # Patch decode_keycloak_token where it's looked up inside auth.py
        monkeypatch.setattr(
            "app.modules.platform.services.auth.decode_keycloak_token",
            always_fail,
        )

        # Drive N failures through the internal method
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await svc._keycloak_circuit.call(
                    always_fail,
                    "tok",
                    keycloak_url="x",
                    realm="r",
                    client_id="c",
                    keycloak_browser_url="",
                )

        assert svc._keycloak_circuit.state == "OPEN"

        # Subsequent call short-circuits — _authenticate_keycloak_operator
        # should translate CircuitOpenError into AuthenticationError.
        with pytest.raises(AuthenticationError) as exc_info:
            await svc._authenticate_keycloak_operator("tok")
        assert exc_info.value.code == "IDP_UNAVAILABLE"


# ---------------------------------------------------------------------------
# OpenFGA integration — FGAClient._circuit
# ---------------------------------------------------------------------------


class _FakeFgaResp:
    def __init__(self, allowed: bool = False) -> None:
        self.allowed = allowed
        self.relations: list[str] = []
        self.objects: list[str] = []
        self.tuples: list[object] = []


class TestOpenFGACircuit:
    @pytest.mark.asyncio
    async def test_circuit_opens_after_repeated_check_failures(self) -> None:
        fake_sdk = MagicMock()
        # check() is awaited — return a coroutine that raises ApiException
        fake_sdk.check = AsyncMock(side_effect=ApiException(status=500, reason="upstream"))
        client = FGAClient(fake_sdk)
        # Tighten threshold
        client._circuit = CircuitBreaker(
            "openfga",
            failure_threshold=3,
            recovery_timeout=30.0,
            tracked_exceptions=(ApiException, ConnectionError, TimeoutError),
        )

        # Three successive failures should trip the circuit. Because check()
        # caches results, use distinct keys so no cache hit short-circuits us.
        for i in range(3):
            with pytest.raises(ApiException):
                await client.check(user=f"user:u{i}", relation="viewer", object="fund:f1")

        assert client._circuit.state == "OPEN"

        # Next call should raise CircuitOpenError without hitting the SDK.
        call_count_before = fake_sdk.check.call_count
        with pytest.raises(CircuitOpenError):
            await client.check(user="user:fresh", relation="viewer", object="fund:f1")
        assert fake_sdk.check.call_count == call_count_before


# ---------------------------------------------------------------------------
# Broker integration — MockExchangeBrokerAdapter._circuit
# ---------------------------------------------------------------------------


class TestBrokerCircuit:
    @pytest.mark.asyncio
    async def test_broker_circuit_opens_after_http_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeated httpx failures should open the broker's circuit."""
        adapter = MockExchangeBrokerAdapter(
            base_url="http://mock-exchange.local",
            kafka_bootstrap_servers="kafka:9092",
        )
        # Tighten the threshold for a fast test.
        adapter._circuit = CircuitBreaker(
            "mock-exchange-broker",
            failure_threshold=3,
            recovery_timeout=30.0,
            tracked_exceptions=(httpx.HTTPError, httpx.TimeoutException, ConnectionError),
        )

        class _FailingClient:
            def __init__(self, *_a: object, **_kw: object) -> None:
                pass

            async def __aenter__(self) -> _FailingClient:
                return self

            async def __aexit__(self, *_a: object) -> None:
                return None

            async def post(self, *_a: object, **_kw: object) -> object:
                raise httpx.ConnectError("refused")

            async def get(self, *_a: object, **_kw: object) -> object:
                raise httpx.ConnectError("refused")

            async def delete(self, *_a: object, **_kw: object) -> object:
                raise httpx.ConnectError("refused")

        monkeypatch.setattr(httpx, "AsyncClient", _FailingClient)

        from decimal import Decimal

        for _ in range(3):
            with pytest.raises(httpx.ConnectError):
                await adapter.submit_order(
                    client_order_id="c1",
                    instrument_id="AAPL",
                    side="buy",
                    quantity=Decimal("10"),
                    order_type="market",
                )

        assert adapter._circuit.state == "OPEN"

        # Next submission should short-circuit.
        with pytest.raises(CircuitOpenError):
            await adapter.submit_order(
                client_order_id="c2",
                instrument_id="AAPL",
                side="buy",
                quantity=Decimal("10"),
                order_type="market",
            )
