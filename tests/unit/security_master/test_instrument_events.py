"""Unit tests for security master instrument event publishing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.security_master.interfaces import AssetClass, Instrument
from app.shared.audit.events import AuditEventType


class TestInstrumentEventTypes:
    def test_instrument_created_type(self) -> None:
        assert AuditEventType.INSTRUMENT_CREATED == "instrument.created"

    def test_instrument_updated_type(self) -> None:
        assert AuditEventType.INSTRUMENT_UPDATED == "instrument.updated"


class TestInstrumentEventPublishing:
    def _make_instrument(self) -> Instrument:
        return Instrument(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            name="Apple Inc.",
            ticker="AAPL",
            asset_class=AssetClass.EQUITY,
            currency="USD",
            exchange="NASDAQ",
            country="US",
            sector="Technology",
        )

    @pytest.mark.asyncio
    async def test_publish_created_event(self) -> None:
        from app.modules.security_master.services.security_master import SecurityMasterService

        mock_bus = AsyncMock()
        service = SecurityMasterService(
            instrument_repo=MagicMock(),
            event_bus=mock_bus,
        )
        instrument = self._make_instrument()
        await service._publish_instrument_event(
            AuditEventType.INSTRUMENT_CREATED,
            instrument,
        )
        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        event = mock_bus.publish.call_args[0][1]
        assert "instruments.created" in topic
        assert event.data["ticker"] == "AAPL"
        assert event.data["instrument_id"] == str(instrument.id)

    @pytest.mark.asyncio
    async def test_publish_updated_event_with_changes(self) -> None:
        from app.modules.security_master.services.security_master import SecurityMasterService

        mock_bus = AsyncMock()
        service = SecurityMasterService(
            instrument_repo=MagicMock(),
            event_bus=mock_bus,
        )
        instrument = self._make_instrument()
        await service._publish_instrument_event(
            AuditEventType.INSTRUMENT_UPDATED,
            instrument,
            changes=["sector", "industry"],
        )
        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        event = mock_bus.publish.call_args[0][1]
        assert "instruments.updated" in topic
        assert event.data["changed_fields"] == ["sector", "industry"]

    @pytest.mark.asyncio
    async def test_publish_skips_when_no_event_bus(self) -> None:
        from app.modules.security_master.services.security_master import SecurityMasterService

        service = SecurityMasterService(
            instrument_repo=MagicMock(),
            event_bus=None,
        )
        instrument = self._make_instrument()
        # Should not raise
        await service._publish_instrument_event(
            AuditEventType.INSTRUMENT_CREATED,
            instrument,
        )

    @pytest.mark.asyncio
    async def test_created_event_uses_shared_topic(self) -> None:
        """Instrument events use shared topics, not fund-scoped."""
        from app.modules.security_master.services.security_master import SecurityMasterService

        mock_bus = AsyncMock()
        service = SecurityMasterService(
            instrument_repo=MagicMock(),
            event_bus=mock_bus,
        )
        instrument = self._make_instrument()
        await service._publish_instrument_event(
            AuditEventType.INSTRUMENT_CREATED,
            instrument,
        )
        topic = mock_bus.publish.call_args[0][0]
        assert topic.startswith("shared.")
