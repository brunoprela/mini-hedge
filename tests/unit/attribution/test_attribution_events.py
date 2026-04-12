"""Unit tests for attribution Kafka event publishing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.audit.events import AuditEventType


class TestAttributionEventPublishing:
    def test_attribution_event_types_exist(self) -> None:
        assert AuditEventType.ATTRIBUTION_DAILY_CALCULATED == "attribution.daily_calculated"
        assert AuditEventType.ATTRIBUTION_CUMULATIVE_UPDATED == "attribution.cumulative_updated"

    @pytest.mark.asyncio
    async def test_publish_helper_skips_when_no_event_bus(self) -> None:
        """When event_bus is None, _publish_attribution_event should be a no-op."""
        from uuid import UUID

        from app.modules.attribution.services.attribution import AttributionService

        service = AttributionService(
            bf_repo=MagicMock(),
            bf_sector_repo=MagicMock(),
            rb_repo=MagicMock(),
            rfc_repo=MagicMock(),
            cum_repo=MagicMock(),
            position_service=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=None,
        )
        # Should not raise
        await service._publish_attribution_event(
            AuditEventType.ATTRIBUTION_DAILY_CALCULATED,
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            data={"test": True},
        )

    @pytest.mark.asyncio
    async def test_publish_helper_calls_event_bus(self) -> None:
        """When event_bus is set and fund_slug is available, event should be published."""
        from uuid import UUID

        from app.modules.attribution.services.attribution import AttributionService

        mock_bus = AsyncMock()
        service = AttributionService(
            bf_repo=MagicMock(),
            bf_sector_repo=MagicMock(),
            rb_repo=MagicMock(),
            rfc_repo=MagicMock(),
            cum_repo=MagicMock(),
            position_service=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=mock_bus,
        )
        with patch(
            "app.shared.database.TenantSessionFactory.current_fund_slug",
            return_value="test-fund",
        ):
            await service._publish_attribution_event(
                AuditEventType.ATTRIBUTION_DAILY_CALCULATED,
                portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
                data={"portfolio_id": "test"},
            )
        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        assert "attribution.daily_calculated" in topic

    @pytest.mark.asyncio
    async def test_publish_skips_when_no_fund_slug(self) -> None:
        from uuid import UUID

        from app.modules.attribution.services.attribution import AttributionService

        mock_bus = AsyncMock()
        service = AttributionService(
            bf_repo=MagicMock(),
            bf_sector_repo=MagicMock(),
            rb_repo=MagicMock(),
            rfc_repo=MagicMock(),
            cum_repo=MagicMock(),
            position_service=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=mock_bus,
        )
        with patch(
            "app.shared.database.TenantSessionFactory.current_fund_slug",
            return_value=None,
        ):
            await service._publish_attribution_event(
                AuditEventType.ATTRIBUTION_DAILY_CALCULATED,
                portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
                data={},
            )
        mock_bus.publish.assert_not_called()
