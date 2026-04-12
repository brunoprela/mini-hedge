"""Unit tests for FeeAccountingService event publishing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.fee_accounting.services.fee import FeeAccountingService
from app.shared.audit.events import AuditEventType


def _make_service(*, with_event_bus: bool = True) -> tuple:
    schedule_repo = AsyncMock()
    accrual_repo = AsyncMock()
    hwm_repo = AsyncMock()
    sf = MagicMock()
    event_bus = AsyncMock() if with_event_bus else None

    # Default schedule mock
    schedule = MagicMock()
    schedule.management_fee_bps = 200
    schedule.performance_fee_pct = Decimal("20")
    schedule.hurdle_rate_pct = Decimal("0")
    schedule.crystallization_frequency = "quarterly"
    schedule_repo.get_by_fund_slug = AsyncMock(return_value=schedule)

    # Default: no prior accruals
    accrual_repo.get_latest_by_type = AsyncMock(return_value=None)
    accrual_repo.insert = AsyncMock(side_effect=lambda rec, **kw: rec)
    accrual_repo.get_by_portfolio = AsyncMock(return_value=[])

    # Default: no HWM
    hwm_repo.get_latest = AsyncMock(return_value=None)

    service = FeeAccountingService(
        session_factory=sf,
        schedule_repo=schedule_repo,
        accrual_repo=accrual_repo,
        hwm_repo=hwm_repo,
        event_bus=event_bus,
    )
    return service, schedule_repo, accrual_repo, hwm_repo, event_bus


class TestAccrualEventPublishing:
    @pytest.mark.asyncio
    async def test_accrue_publishes_event(self) -> None:
        service, _, _, _, event_bus = _make_service()

        await service.accrue_daily_fees(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            fund_slug="alpha",
            nav=Decimal("100000000"),
            business_date=date(2026, 4, 10),
        )

        event_bus.publish.assert_called_once()
        topic, event = event_bus.publish.call_args.args
        assert "fees.accrued" in topic
        assert "alpha" in topic
        assert event.event_type == AuditEventType.FEES_ACCRUED
        assert event.fund_slug == "alpha"
        assert event.data["portfolio_id"] == "00000000-0000-0000-0000-000000000001"

    @pytest.mark.asyncio
    async def test_accrue_no_event_without_bus(self) -> None:
        service, _, _, _, _ = _make_service(with_event_bus=False)

        accruals = await service.accrue_daily_fees(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            fund_slug="alpha",
            nav=Decimal("100000000"),
            business_date=date(2026, 4, 10),
        )
        assert len(accruals) >= 1  # At least management fee

    @pytest.mark.asyncio
    async def test_accrue_no_event_when_no_schedule(self) -> None:
        service, schedule_repo, _, _, event_bus = _make_service()
        schedule_repo.get_by_fund_slug = AsyncMock(return_value=None)

        accruals = await service.accrue_daily_fees(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            fund_slug="alpha",
            nav=Decimal("100000000"),
            business_date=date(2026, 4, 10),
        )
        assert accruals == []
        event_bus.publish.assert_not_called()


class TestCrystallizationEventPublishing:
    @pytest.mark.asyncio
    async def test_crystallize_publishes_event(self) -> None:
        service, _, accrual_repo, hwm_repo, event_bus = _make_service()

        # Simulate accrued records that need crystallizing
        accrual = MagicMock()
        accrual.status = "accrued"
        accrual.share_class = "default"
        accrual.nav_basis = Decimal("100000000")
        accrual.id = "00000000-0000-0000-0000-000000000099"
        accrual_repo.get_by_portfolio = AsyncMock(return_value=[accrual])
        hwm_repo.upsert = AsyncMock()

        await service.crystallize_fees(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            fund_slug="alpha",
            business_date=date(2026, 3, 31),  # Quarter end
        )

        event_bus.publish.assert_called_once()
        topic, event = event_bus.publish.call_args.args
        assert "fees.crystallized" in topic
        assert event.event_type == AuditEventType.FEES_CRYSTALLIZED

    @pytest.mark.asyncio
    async def test_crystallize_skips_non_boundary(self) -> None:
        service, _, _, _, event_bus = _make_service()

        await service.crystallize_fees(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            fund_slug="alpha",
            business_date=date(2026, 4, 10),  # Not a quarter end
        )

        event_bus.publish.assert_not_called()
