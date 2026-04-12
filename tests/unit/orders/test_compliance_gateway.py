"""Unit tests for ComplianceGateway."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.modules.orders.core.compliance_gateway import ComplianceGateway


class TestComplianceGateway:
    async def test_delegates_to_pre_trade_gate(self) -> None:
        pre_trade_gate = AsyncMock()
        expected = MagicMock()
        pre_trade_gate.check_trade.return_value = expected

        gw = ComplianceGateway(pre_trade_gate=pre_trade_gate)
        request = MagicMock()

        result = await gw.check(request)

        assert result is expected
        pre_trade_gate.check_trade.assert_awaited_once_with(request)
