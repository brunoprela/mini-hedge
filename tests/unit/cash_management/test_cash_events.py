"""Unit tests for cash management event publishing (projected, settlement_due, balance_warning)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.cash_management.interfaces import CashProjection, CashProjectionEntry
from app.shared.audit.events import AuditEventType

_PID = UUID("00000000-0000-0000-0000-000000000001")


class TestCashEventTypes:
    def test_cash_projected_event_type(self) -> None:
        assert AuditEventType.CASH_PROJECTED == "cash.projected"

    def test_cash_settlement_due_event_type(self) -> None:
        assert AuditEventType.CASH_SETTLEMENT_DUE == "cash.settlement_due"

    def test_cash_balance_warning_event_type(self) -> None:
        assert AuditEventType.CASH_BALANCE_WARNING == "cash.balance_warning"


class TestCashProjectedPublishing:
    def _make_service(self, *, event_bus=None):
        from app.modules.cash_management.services.cash import CashManagementService

        return CashManagementService(
            session_factory=MagicMock(),
            balance_repo=MagicMock(),
            journal_repo=MagicMock(),
            settlement_repo=MagicMock(),
            scheduled_flow_repo=MagicMock(),
            projection_repo=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=event_bus,
        )

    def _make_projection(self, entries=None) -> CashProjection:
        return CashProjection(
            portfolio_id=_PID,
            base_currency="USD",
            horizon_days=30,
            entries=entries or [],
            projected_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_publish_cash_projected_skips_without_bus(self) -> None:
        service = self._make_service(event_bus=None)
        projection = self._make_projection()
        # Should not raise
        await service._publish_cash_projected(_PID, projection, "test-fund")

    @pytest.mark.asyncio
    async def test_publish_cash_projected_skips_without_fund_slug(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        projection = self._make_projection()
        await service._publish_cash_projected(_PID, projection, None)
        mock_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_cash_projected_calls_event_bus(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        entries = [
            CashProjectionEntry(
                projection_date=date.today(),
                currency="USD",
                opening_balance=Decimal("100000"),
                inflows=Decimal("0"),
                outflows=Decimal("0"),
                closing_balance=Decimal("100000"),
                flow_details=[],
            ),
        ]
        projection = self._make_projection(entries=entries)
        await service._publish_cash_projected(_PID, projection, "alpha-fund")
        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        assert "cash.projected" in topic
        event = mock_bus.publish.call_args[0][1]
        assert event.event_type == AuditEventType.CASH_PROJECTED
        assert event.data["horizon_days"] == 30
        assert event.data["entries_count"] == 1


class TestSettlementDuePublishing:
    def _make_service(self, *, event_bus=None):
        from app.modules.cash_management.services.cash import CashManagementService

        return CashManagementService(
            session_factory=MagicMock(),
            balance_repo=MagicMock(),
            journal_repo=MagicMock(),
            settlement_repo=MagicMock(),
            scheduled_flow_repo=MagicMock(),
            projection_repo=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_publish_settlement_due_calls_event_bus(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        settle_date = date.today() + timedelta(days=1)
        await service._publish_settlement_due(
            "00000000-0000-0000-0000-000000000001",
            "AAPL",
            Decimal("50000"),
            settle_date,
            "alpha-fund",
        )
        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][1]
        assert event.event_type == AuditEventType.CASH_SETTLEMENT_DUE
        assert event.data["instrument_id"] == "AAPL"
        assert event.data["amount"] == "50000"
        assert event.data["days_until_due"] == 1

    @pytest.mark.asyncio
    async def test_publish_settlement_due_skips_without_fund(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        await service._publish_settlement_due(
            "00000000-0000-0000-0000-000000000001",
            "AAPL",
            Decimal("50000"),
            date.today(),
            None,
        )
        mock_bus.publish.assert_not_called()


class TestBalanceWarningPublishing:
    def _make_service(self, *, event_bus=None):
        from app.modules.cash_management.services.cash import CashManagementService

        return CashManagementService(
            session_factory=MagicMock(),
            balance_repo=MagicMock(),
            journal_repo=MagicMock(),
            settlement_repo=MagicMock(),
            scheduled_flow_repo=MagicMock(),
            projection_repo=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=event_bus,
        )

    @pytest.mark.asyncio
    async def test_publish_balance_warning_calls_event_bus(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        warning_date = date.today() + timedelta(days=5)
        await service._publish_balance_warning(
            "00000000-0000-0000-0000-000000000001",
            Decimal("-5000"),
            warning_date,
            "alpha-fund",
        )
        mock_bus.publish.assert_called_once()
        event = mock_bus.publish.call_args[0][1]
        assert event.event_type == AuditEventType.CASH_BALANCE_WARNING
        assert event.data["projected_balance"] == "-5000"
        assert event.data["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_publish_balance_warning_skips_without_bus(self) -> None:
        service = self._make_service(event_bus=None)
        await service._publish_balance_warning(
            "00000000-0000-0000-0000-000000000001",
            Decimal("-5000"),
            date.today(),
            "alpha-fund",
        )
        # Should not raise
