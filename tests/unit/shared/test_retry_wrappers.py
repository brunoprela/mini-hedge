"""Verify tenacity retries kick in for transient failures.

These tests exercise the retry wrappers wired around Keycloak JWKS
fetches, OpenFGA SDK calls, and broker-adapter HTTP requests.  The
contract under test is: a single transient failure is retried and the
call succeeds on the second attempt — without the circuit breaker
observing a failure.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.adapters.mock_exchange_broker import (
    MockExchangeBrokerAdapter,
    _retry_http,
)
from app.shared.circuit_breaker import CircuitBreaker
from app.shared.fga.client import FGAClient


class TestRetryOnTransient:
    """One failure → retry → success.  Circuit stays CLOSED."""

    @pytest.mark.asyncio
    async def test_broker_http_retry_succeeds_on_second_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single ConnectError should be retried and succeed on attempt #2."""
        adapter = MockExchangeBrokerAdapter(
            base_url="http://mock-exchange.local",
            kafka_bootstrap_servers="kafka:9092",
        )

        # Track how many times post() is invoked.  First call raises, second
        # returns a success.
        call_count = {"n": 0}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "exchange_order_id": "ex-1",
                    "client_order_id": "c1",
                    "status": "accepted",
                    "received_at": "2025-01-01T00:00:00+00:00",
                }

        class _FlakyClient:
            def __init__(self, *_a: object, **_kw: object) -> None:
                pass

            async def __aenter__(self) -> "_FlakyClient":
                return self

            async def __aexit__(self, *_a: object) -> None:
                return None

            async def post(self, *_a: object, **_kw: object) -> _Response:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise httpx.ConnectError("transient — refused once")
                return _Response()

            async def get(self, *_a: object, **_kw: object) -> _Response:
                return _Response()

            async def delete(self, *_a: object, **_kw: object) -> _Response:
                return _Response()

        monkeypatch.setattr(httpx, "AsyncClient", _FlakyClient)

        ack = await adapter.submit_order(
            client_order_id="c1",
            instrument_id="AAPL",
            side="buy",
            quantity=Decimal("10"),
            order_type="market",
        )

        # The retry fired: post() was called twice, but the adapter
        # returned a successful acknowledgement.
        assert call_count["n"] == 2
        assert ack.client_order_id == "c1"
        assert ack.status == "accepted"
        # Circuit breaker never saw a failure because the retry absorbed it.
        assert adapter._circuit.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_fga_retry_succeeds_on_second_attempt(self) -> None:
        """A transient ServiceException from the FGA SDK should be retried."""
        from openfga_sdk.exceptions import ServiceException

        calls = {"n": 0}

        async def flaky_check(**_kwargs: object) -> MagicMock:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ServiceException(status=503, reason="upstream flap")
            resp = MagicMock()
            resp.allowed = True
            return resp

        fake_sdk = MagicMock()
        fake_sdk.check = flaky_check
        client = FGAClient(fake_sdk)

        allowed = await client.check(
            user="user:u1", relation="viewer", object="fund:f1",
        )
        assert allowed is True
        assert calls["n"] == 2
        # Circuit stayed CLOSED because the retry absorbed the single failure.
        assert client._circuit.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_retry_http_helper_reraises_after_three_attempts(self) -> None:
        """After three transient failures, the wrapper re-raises."""
        attempts = {"n": 0}

        async def always_fail() -> None:
            attempts["n"] += 1
            raise httpx.ConnectError("nope")

        with pytest.raises(httpx.ConnectError):
            await _retry_http(always_fail)

        assert attempts["n"] == 3
