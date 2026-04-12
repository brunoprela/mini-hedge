"""Unit tests for risk limit breach event publishing."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.risk_engine.models.risk_snapshot import RiskSnapshotRecord
from app.shared.audit.events import AuditEventType


class TestRiskLimitBreachEventType:
    def test_event_type_value(self) -> None:
        assert AuditEventType.RISK_LIMIT_BREACHED == "risk.limit_breached"


class TestRiskLimitBreachPublishing:
    def _make_service(self, *, event_bus=None, var_limit_pct: float = 5.0):
        from app.modules.risk_engine.services.snapshot import RiskSnapshotService

        return RiskSnapshotService(
            snapshot_repo=MagicMock(),
            var_result_repo=MagicMock(),
            var_contribution_repo=MagicMock(),
            stress_result_repo=MagicMock(),
            stress_impact_repo=MagicMock(),
            factor_repo=MagicMock(),
            position_service=MagicMock(),
            market_data_service=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=event_bus,
            var_limit_pct=var_limit_pct,
        )

    def _make_record(self, *, var_95: Decimal, nav: Decimal) -> RiskSnapshotRecord:
        record = MagicMock(spec=RiskSnapshotRecord)
        record.var_95_1d = var_95
        record.nav = nav
        record.portfolio_id = "00000000-0000-0000-0000-000000000001"
        return record

    @pytest.mark.asyncio
    async def test_publish_skips_when_no_event_bus(self) -> None:
        service = self._make_service(event_bus=None)
        record = self._make_record(var_95=Decimal("600"), nav=Decimal("10000"))
        # Should not raise
        await service._publish_limit_breach(record, "test-fund", 6.0)

    @pytest.mark.asyncio
    async def test_publish_skips_when_no_fund_slug(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        record = self._make_record(var_95=Decimal("600"), nav=Decimal("10000"))
        await service._publish_limit_breach(record, None, 6.0)
        mock_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_calls_event_bus_on_breach(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus, var_limit_pct=5.0)
        record = self._make_record(var_95=Decimal("600"), nav=Decimal("10000"))
        await service._publish_limit_breach(record, "test-fund", 6.0)

        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        assert "risk.limit_breached" in topic
        event = mock_bus.publish.call_args[0][1]
        assert event.event_type == AuditEventType.RISK_LIMIT_BREACHED
        assert event.data["breach_type"] == "var_95_1d"
        assert event.data["var_pct_of_nav"] == "6.00"
        assert event.data["limit_pct"] == "5.0"

    @pytest.mark.asyncio
    async def test_event_data_contains_portfolio_and_nav(self) -> None:
        mock_bus = AsyncMock()
        service = self._make_service(event_bus=mock_bus)
        record = self._make_record(var_95=Decimal("800"), nav=Decimal("10000"))
        await service._publish_limit_breach(record, "alpha-fund", 8.0)

        event = mock_bus.publish.call_args[0][1]
        assert event.data["portfolio_id"] == "00000000-0000-0000-0000-000000000001"
        assert event.data["var_95_1d"] == "800"
        assert event.data["nav"] == "10000"
        assert event.fund_slug == "alpha-fund"
