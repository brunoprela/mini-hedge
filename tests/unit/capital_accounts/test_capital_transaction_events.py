"""Unit tests for CapitalTransactionService event publishing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.capital_accounts.models.capital_account import CapitalAccountRecord
from app.modules.capital_accounts.services.capital_transaction import (
    CapitalTransactionService,
)
from app.shared.audit.events import AuditEventType


def _make_account(
    *,
    id: str = "acct-1",
    investor_id: str = "inv-1",
    ending_capital: Decimal = Decimal("1000000"),
    ownership_pct: Decimal = Decimal("1.0"),
    shares_held: Decimal = Decimal("10000"),
    share_class: str = "default",
    effective_date: date | None = None,
) -> MagicMock:
    a = MagicMock(spec=CapitalAccountRecord)
    a.id = id
    a.investor_id = investor_id
    a.ending_capital = ending_capital
    a.ownership_pct = ownership_pct
    a.shares_held = shares_held
    a.share_class = share_class
    a.effective_date = effective_date or date(2026, 4, 10)
    return a


def _make_service(*, with_event_bus: bool = True) -> tuple:
    account_repo = AsyncMock()
    transaction_repo = AsyncMock()
    event_bus = AsyncMock() if with_event_bus else None

    # Default: insert returns its input
    account_repo.insert = AsyncMock(side_effect=lambda rec, **kw: rec)
    transaction_repo.insert = AsyncMock()

    service = CapitalTransactionService(
        account_repo=account_repo,
        transaction_repo=transaction_repo,
        event_bus=event_bus,
    )
    return service, account_repo, transaction_repo, event_bus


class TestSubscriptionEventPublishing:
    @pytest.mark.asyncio
    async def test_subscription_publishes_event(self) -> None:
        service, account_repo, _, event_bus = _make_service()
        account_repo.get_latest_for_investor = AsyncMock(return_value=None)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        await service.process_subscription(
            investor_id="inv-1",
            amount=Decimal("500000"),
            nav_per_share=Decimal("100"),
            business_date=date(2026, 4, 10),
        )

        event_bus.publish.assert_called_once()
        topic, event = event_bus.publish.call_args.args
        assert "capital.subscription" in topic
        assert event.event_type == AuditEventType.CAPITAL_SUBSCRIPTION
        assert event.data["investor_id"] == "inv-1"
        assert event.data["amount"] == "500000"

    @pytest.mark.asyncio
    async def test_subscription_no_event_without_bus(self) -> None:
        service, account_repo, _, _ = _make_service(with_event_bus=False)
        account_repo.get_latest_for_investor = AsyncMock(return_value=None)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        # Should not raise even without event_bus
        await service.process_subscription(
            investor_id="inv-1",
            amount=Decimal("500000"),
            nav_per_share=Decimal("100"),
            business_date=date(2026, 4, 10),
        )


class TestRedemptionEventPublishing:
    @pytest.mark.asyncio
    async def test_redemption_publishes_event(self) -> None:
        service, account_repo, _, event_bus = _make_service()
        existing = _make_account(ending_capital=Decimal("1000000"))
        account_repo.get_latest_for_investor = AsyncMock(return_value=existing)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        await service.process_redemption(
            investor_id="inv-1",
            amount=Decimal("200000"),
            nav_per_share=Decimal("100"),
            business_date=date(2026, 4, 10),
        )

        event_bus.publish.assert_called_once()
        topic, event = event_bus.publish.call_args.args
        assert "capital.redemption" in topic
        assert event.event_type == AuditEventType.CAPITAL_REDEMPTION
        assert event.data["investor_id"] == "inv-1"
        assert event.data["amount"] == "200000"

    @pytest.mark.asyncio
    async def test_redemption_exceeding_capital_raises(self) -> None:
        service, account_repo, _, event_bus = _make_service()
        existing = _make_account(ending_capital=Decimal("100"))
        account_repo.get_latest_for_investor = AsyncMock(return_value=existing)

        with pytest.raises(ValueError, match="exceeds ending capital"):
            await service.process_redemption(
                investor_id="inv-1",
                amount=Decimal("500"),
                nav_per_share=Decimal("100"),
                business_date=date(2026, 4, 10),
            )

        event_bus.publish.assert_not_called()


class TestAllocationEventPublishing:
    @pytest.mark.asyncio
    async def test_allocation_publishes_event(self) -> None:
        service, account_repo, _, event_bus = _make_service()
        acct = _make_account(
            ending_capital=Decimal("1000000"),
            ownership_pct=Decimal("1.0"),
            effective_date=date(2026, 4, 10),
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        count = await service.allocate_daily(
            fund_pnl=Decimal("50000"),
            management_fee=Decimal("500"),
            performance_fee=Decimal("1000"),
            nav_per_share=Decimal("105"),
            business_date=date(2026, 4, 10),
        )

        assert count == 1
        event_bus.publish.assert_called_once()
        topic, event = event_bus.publish.call_args.args
        assert "capital.allocation" in topic
        assert event.event_type == AuditEventType.CAPITAL_ALLOCATION
        assert event.data["accounts_allocated"] == 1
        assert event.data["fund_pnl"] == "50000"

    @pytest.mark.asyncio
    async def test_allocation_no_accounts_no_event(self) -> None:
        service, account_repo, _, event_bus = _make_service()
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        count = await service.allocate_daily(
            fund_pnl=Decimal("50000"),
            management_fee=Decimal("500"),
            performance_fee=Decimal("1000"),
            nav_per_share=Decimal("105"),
            business_date=date(2026, 4, 10),
        )

        assert count == 0
        event_bus.publish.assert_not_called()
