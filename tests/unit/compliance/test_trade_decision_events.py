"""Unit tests for compliance trade decision event publishing."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.modules.compliance.interfaces import ComplianceDecision, TradeCheckRequest
from app.shared.audit.events import AuditEventType


class TestTradeDecisionEventTypes:
    def test_trade_approved_type(self) -> None:
        assert AuditEventType.TRADE_APPROVED == "trade.approved"

    def test_trade_rejected_type(self) -> None:
        assert AuditEventType.TRADE_REJECTED == "trade.rejected"


class TestTradeDecisionPublishing:
    def _make_service(self, event_bus=None):
        from app.modules.compliance.services.compliance import ComplianceService

        return ComplianceService(
            rule_repo=MagicMock(),
            violation_repo=MagicMock(),
            pre_trade_gate=MagicMock(),
            event_bus=event_bus,
        )

    def _make_request(self) -> TradeCheckRequest:
        return TradeCheckRequest(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            instrument_id="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
        )

    @pytest.mark.asyncio
    async def test_publish_approved_event(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        request = self._make_request()
        decision = ComplianceDecision(approved=True, results=[], blocked_by=[])

        with patch(
            "app.modules.compliance.services.compliance.TenantSessionFactory.current_fund_slug",
            return_value="test-fund",
        ):
            await service._publish_trade_decision(request, decision)

        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        event = mock_bus.publish.call_args[0][1]
        assert "trades.approved" in topic
        assert event.event_type == AuditEventType.TRADE_APPROVED
        assert event.data["approved"] is True

    @pytest.mark.asyncio
    async def test_publish_rejected_event(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        request = self._make_request()
        decision = ComplianceDecision(
            approved=False, results=[], blocked_by=["CONCENTRATION_LIMIT"]
        )

        with patch(
            "app.modules.compliance.services.compliance.TenantSessionFactory.current_fund_slug",
            return_value="test-fund",
        ):
            await service._publish_trade_decision(request, decision)

        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        event = mock_bus.publish.call_args[0][1]
        assert "trades.rejected" in topic
        assert event.event_type == AuditEventType.TRADE_REJECTED
        assert event.data["approved"] is False
        assert event.data["blocked_by"] == ["CONCENTRATION_LIMIT"]

    @pytest.mark.asyncio
    async def test_publish_skips_when_no_event_bus(self) -> None:
        service = self._make_service(event_bus=None)
        request = self._make_request()
        decision = ComplianceDecision(approved=True, results=[], blocked_by=[])
        # Should not raise
        await service._publish_trade_decision(request, decision)

    @pytest.mark.asyncio
    async def test_publish_skips_when_no_fund_slug(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        request = self._make_request()
        decision = ComplianceDecision(approved=True, results=[], blocked_by=[])

        with patch(
            "app.modules.compliance.services.compliance.TenantSessionFactory.current_fund_slug",
            return_value=None,
        ):
            await service._publish_trade_decision(request, decision)
        mock_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_trade_publishes_event(self) -> None:
        """Integration: check_trade calls the gate and then publishes."""
        mock_bus = AsyncMock()
        mock_gate = AsyncMock()
        decision = ComplianceDecision(approved=True, results=[], blocked_by=[])
        mock_gate.check_trade.return_value = decision

        from app.modules.compliance.services.compliance import ComplianceService

        service = ComplianceService(
            rule_repo=MagicMock(),
            violation_repo=MagicMock(),
            pre_trade_gate=mock_gate,
            event_bus=mock_bus,
        )
        request = self._make_request()

        with patch(
            "app.modules.compliance.services.compliance.TenantSessionFactory.current_fund_slug",
            return_value="test-fund",
        ):
            result = await service.check_trade(request)

        assert result.approved is True
        mock_gate.check_trade.assert_called_once_with(request)
        mock_bus.publish.assert_called_once()
