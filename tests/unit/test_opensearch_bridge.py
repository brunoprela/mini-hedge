"""Unit tests for the OpenSearch bridge and client wrapper."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.shared.events import BaseEvent, InProcessEventBus
from app.shared.opensearch_bridge import OpenSearchBridge
from app.shared.opensearch_client import OpenSearchClient, _index_name
from app.shared.schema_registry import fund_topic

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_os_client() -> AsyncMock:
    client = AsyncMock(spec=OpenSearchClient)
    client.index_event = AsyncMock()
    client.search = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


@pytest.fixture
def bridge(mock_os_client: AsyncMock) -> OpenSearchBridge:
    return OpenSearchBridge(mock_os_client)


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
# Index Name Tests
# ---------------------------------------------------------------------------


class TestIndexName:
    def test_fund_slug(self) -> None:
        assert _index_name("alpha") == "audit-fund-alpha"

    def test_no_fund_slug(self) -> None:
        assert _index_name(None) == "audit-platform"


# ---------------------------------------------------------------------------
# OpenSearchBridge Tests
# ---------------------------------------------------------------------------


class TestOpenSearchBridge:
    def test_wire_subscribes_to_fund_topics(
        self, bridge: OpenSearchBridge, event_bus: InProcessEventBus
    ) -> None:
        bridge.wire(event_bus, ["alpha"])

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
    async def test_handler_indexes_to_opensearch(
        self,
        bridge: OpenSearchBridge,
        mock_os_client: AsyncMock,
        event_bus: InProcessEventBus,
    ) -> None:
        bridge.wire(event_bus, ["alpha"])

        event = _make_event()
        await event_bus.publish(fund_topic("alpha", "trades.executed"), event)

        mock_os_client.index_event.assert_called_once()
        call_kwargs = mock_os_client.index_event.call_args.kwargs
        assert call_kwargs["event_id"] == "evt-001"
        assert call_kwargs["event_type"] == "trades.executed"
        assert call_kwargs["fund_slug"] == "alpha"
        assert call_kwargs["data"]["instrument_id"] == "AAPL"

    @pytest.mark.asyncio
    async def test_handler_increments_counter(
        self,
        bridge: OpenSearchBridge,
        event_bus: InProcessEventBus,
    ) -> None:
        bridge.wire(event_bus, ["alpha"])

        assert bridge.events_indexed == 0
        await event_bus.publish(fund_topic("alpha", "trades.executed"), _make_event())
        assert bridge.events_indexed == 1

    @pytest.mark.asyncio
    async def test_handler_swallows_errors(
        self,
        bridge: OpenSearchBridge,
        mock_os_client: AsyncMock,
        event_bus: InProcessEventBus,
    ) -> None:
        mock_os_client.index_event.side_effect = ConnectionError("opensearch down")
        bridge.wire(event_bus, ["alpha"])

        # Should not raise
        await event_bus.publish(fund_topic("alpha", "trades.executed"), _make_event())
        assert bridge.events_indexed == 0


# ---------------------------------------------------------------------------
# OpenSearchClient Tests (mocked SDK)
# ---------------------------------------------------------------------------


class TestOpenSearchClient:
    @pytest.mark.asyncio
    async def test_close_when_not_connected(self) -> None:
        client = OpenSearchClient()
        # Should not raise
        await client.close()
