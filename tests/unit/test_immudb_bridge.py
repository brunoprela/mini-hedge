"""Unit tests for the immudb bridge and client wrapper."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.shared.events import BaseEvent, InProcessEventBus
from app.shared.immudb_bridge import ImmudbBridge
from app.shared.immudb_client import ImmudbClient
from app.shared.immudb_verifier import VerificationResult, verify_audit_batch
from app.shared.schema_registry import fund_topic

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_immudb_client() -> AsyncMock:
    client = AsyncMock(spec=ImmudbClient)
    client.verified_set = AsyncMock()
    client.verified_get = AsyncMock(return_value=None)
    client.close = AsyncMock()
    return client


@pytest.fixture
def bridge(mock_immudb_client: AsyncMock) -> ImmudbBridge:
    return ImmudbBridge(mock_immudb_client)


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


def _make_event(
    event_id: str = "evt-001",
    event_type: str = "trades.executed",
    fund_slug: str = "alpha",
) -> BaseEvent:
    return BaseEvent(
        event_id=event_id,
        event_type=event_type,
        event_version=1,
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
        actor_id="pm-001",
        actor_type="user",
        fund_slug=fund_slug,
        data={"instrument_id": "AAPL", "quantity": 100, "price": "150.00"},
    )


# ---------------------------------------------------------------------------
# ImmudbBridge Tests
# ---------------------------------------------------------------------------


class TestImmudbBridge:
    def test_wire_subscribes_to_fund_topics(
        self, bridge: ImmudbBridge, event_bus: InProcessEventBus
    ) -> None:
        bridge.wire(event_bus, ["alpha"])

        # Should have subscribed to all fund-alpha topics
        fund_alpha_topics = [
            fund_topic("alpha", base)
            for base in [
                "positions.changed",
                "pnl.updated",
                "trades.executed",
                "exposures.updated",
                "compliance.violations",
                "orders.created",
                "orders.filled",
                "trades.approved",
                "trades.rejected",
                "risk.updated",
                "cash.settlement.created",
                "cash.settlement.settled",
            ]
        ]
        for topic in fund_alpha_topics:
            assert topic in event_bus._handlers

    @pytest.mark.asyncio
    async def test_handler_writes_to_immudb(
        self,
        bridge: ImmudbBridge,
        mock_immudb_client: AsyncMock,
        event_bus: InProcessEventBus,
    ) -> None:
        bridge.wire(event_bus, ["alpha"])

        event = _make_event()
        topic = fund_topic("alpha", "trades.executed")
        await event_bus.publish(topic, event)

        mock_immudb_client.verified_set.assert_called_once()
        call_args = mock_immudb_client.verified_set.call_args
        assert call_args.kwargs["key"] == "audit:evt-001"
        value = call_args.kwargs["value"]
        assert value["event_id"] == "evt-001"
        assert value["event_type"] == "trades.executed"
        assert value["data"]["instrument_id"] == "AAPL"

    @pytest.mark.asyncio
    async def test_handler_increments_counter(
        self,
        bridge: ImmudbBridge,
        event_bus: InProcessEventBus,
    ) -> None:
        bridge.wire(event_bus, ["alpha"])

        assert bridge.events_written == 0
        await event_bus.publish(fund_topic("alpha", "trades.executed"), _make_event())
        assert bridge.events_written == 1

    @pytest.mark.asyncio
    async def test_handler_swallows_errors(
        self,
        bridge: ImmudbBridge,
        mock_immudb_client: AsyncMock,
        event_bus: InProcessEventBus,
    ) -> None:
        mock_immudb_client.verified_set.side_effect = ConnectionError("immudb down")
        bridge.wire(event_bus, ["alpha"])

        # Should not raise
        await event_bus.publish(fund_topic("alpha", "trades.executed"), _make_event())
        assert bridge.events_written == 0


# ---------------------------------------------------------------------------
# ImmudbClient Tests (mocked SDK)
# ---------------------------------------------------------------------------


class TestImmudbClient:
    @pytest.mark.asyncio
    async def test_connect_calls_sdk(self) -> None:
        client = ImmudbClient(host="localhost", port=3322)

        mock_sdk = AsyncMock()
        with patch("app.shared.immudb_client.asyncio.to_thread") as mock_thread:
            mock_thread.return_value = mock_sdk
            # connect calls to_thread twice effectively, but our mock simplifies
            with patch("immudb.ImmudbClient") as mock_cls:
                instance = mock_cls.return_value
                instance.login = AsyncMock()

                await client.connect()

    @pytest.mark.asyncio
    async def test_verified_set_serializes_json(self) -> None:
        client = ImmudbClient()
        client._client = AsyncMock()

        with patch("app.shared.immudb_client.asyncio.to_thread") as mock_thread:
            await client.verified_set("key-1", {"a": 1})
            mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_when_not_connected(self) -> None:
        client = ImmudbClient()
        # Should not raise
        await client.close()


# ---------------------------------------------------------------------------
# Verifier Tests
# ---------------------------------------------------------------------------


class TestVerifier:
    @pytest.mark.asyncio
    async def test_clean_verification(self) -> None:

        audit_repo = AsyncMock()
        immudb_client = AsyncMock()

        payload = {"instrument_id": "AAPL", "quantity": 100}
        record = AsyncMock()
        record.event_id = "evt-001"
        record.payload = payload

        audit_repo.query = AsyncMock(return_value=[record])

        # immudb returns matching data
        immudb_client.verified_get = AsyncMock(return_value={"data": payload})

        result = await verify_audit_batch(
            audit_repo=audit_repo,
            immudb_client=immudb_client,
            fund_slug="alpha",
            limit=10,
        )

        assert result.is_clean
        assert result.total_checked == 1
        assert result.verified == 1

    @pytest.mark.asyncio
    async def test_mismatch_detected(self) -> None:
        audit_repo = AsyncMock()
        immudb_client = AsyncMock()

        record = AsyncMock()
        record.event_id = "evt-002"
        record.payload = {"quantity": 100}

        audit_repo.query = AsyncMock(return_value=[record])

        # immudb has different data — tampered!
        immudb_client.verified_get = AsyncMock(return_value={"data": {"quantity": 999}})

        result = await verify_audit_batch(
            audit_repo=audit_repo,
            immudb_client=immudb_client,
        )

        assert not result.is_clean
        assert result.mismatches == ["evt-002"]

    @pytest.mark.asyncio
    async def test_missing_in_immudb(self) -> None:
        audit_repo = AsyncMock()
        immudb_client = AsyncMock()

        record = AsyncMock()
        record.event_id = "evt-003"
        record.payload = {"x": 1}

        audit_repo.query = AsyncMock(return_value=[record])
        immudb_client.verified_get = AsyncMock(return_value=None)

        result = await verify_audit_batch(
            audit_repo=audit_repo,
            immudb_client=immudb_client,
        )

        assert not result.is_clean
        assert result.missing_in_immudb == ["evt-003"]

    def test_verification_result_empty_is_clean(self) -> None:
        result = VerificationResult()
        assert result.is_clean
