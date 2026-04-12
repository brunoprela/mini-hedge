"""Unit tests for alpha engine Kafka event publishing."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.modules.alpha_engine.interfaces import OptimizationObjective, OptimizationResult, OrderIntent
from app.shared.audit.events import AuditEventType


class TestAlphaEventTypes:
    def test_order_intents_generated_event_type(self) -> None:
        assert AuditEventType.ORDER_INTENTS_GENERATED == "order_intents.generated"


class TestAlphaEventPublishing:
    @pytest.mark.asyncio
    async def test_publish_skips_when_no_event_bus(self) -> None:
        from app.modules.alpha_engine.services.alpha import AlphaService

        service = AlphaService(
            scenario_repo=MagicMock(),
            opt_run_repo=MagicMock(),
            opt_weight_repo=MagicMock(),
            intent_repo=MagicMock(),
            position_service=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=None,
        )
        result = OptimizationResult(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            objective=OptimizationObjective.MAX_SHARPE,
            expected_return=Decimal("0.08"),
            expected_risk=Decimal("0.15"),
            weights=[],
            order_intents=[
                OrderIntent(
                    instrument_id="AAPL",
                    side="buy",
                    quantity=Decimal("100"),
                    estimated_value=Decimal("15000"),
                    reason="optimization",
                )
            ],
            calculated_at=datetime.now(UTC),
        )
        # Should not raise
        await service._publish_intents_event(result.portfolio_id, result)

    @pytest.mark.asyncio
    async def test_publish_calls_event_bus(self) -> None:
        from app.modules.alpha_engine.services.alpha import AlphaService

        mock_bus = AsyncMock()
        service = AlphaService(
            scenario_repo=MagicMock(),
            opt_run_repo=MagicMock(),
            opt_weight_repo=MagicMock(),
            intent_repo=MagicMock(),
            position_service=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=mock_bus,
        )
        result = OptimizationResult(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            objective=OptimizationObjective.MAX_SHARPE,
            expected_return=Decimal("0.08"),
            expected_risk=Decimal("0.15"),
            weights=[],
            order_intents=[
                OrderIntent(
                    instrument_id="AAPL",
                    side="buy",
                    quantity=Decimal("100"),
                    estimated_value=Decimal("15000"),
                    reason="optimization",
                )
            ],
            calculated_at=datetime.now(UTC),
        )
        with patch(
            "app.shared.database.TenantSessionFactory.current_fund_slug",
            return_value="alpha-fund",
        ):
            await service._publish_intents_event(result.portfolio_id, result)

        mock_bus.publish.assert_called_once()
        topic = mock_bus.publish.call_args[0][0]
        assert "order_intents.generated" in topic
        event = mock_bus.publish.call_args[0][1]
        assert event.data["intent_count"] == 1
        assert event.data["intents"][0]["instrument_id"] == "AAPL"

    @pytest.mark.asyncio
    async def test_publish_skips_when_no_fund_slug(self) -> None:
        from app.modules.alpha_engine.services.alpha import AlphaService

        mock_bus = AsyncMock()
        service = AlphaService(
            scenario_repo=MagicMock(),
            opt_run_repo=MagicMock(),
            opt_weight_repo=MagicMock(),
            intent_repo=MagicMock(),
            position_service=MagicMock(),
            security_master_service=MagicMock(),
            event_bus=mock_bus,
        )
        result = OptimizationResult(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            objective=OptimizationObjective.MAX_SHARPE,
            expected_return=Decimal("0.08"),
            expected_risk=Decimal("0.15"),
            weights=[],
            order_intents=[
                OrderIntent(instrument_id="AAPL", side="buy", quantity=Decimal("100"),
                            estimated_value=Decimal("15000"), reason="opt")
            ],
            calculated_at=datetime.now(UTC),
        )
        with patch(
            "app.shared.database.TenantSessionFactory.current_fund_slug",
            return_value=None,
        ):
            await service._publish_intents_event(result.portfolio_id, result)
        mock_bus.publish.assert_not_called()
