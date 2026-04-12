"""Unit tests for CapitalTransactionService — uncovered branches."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.modules.capital_accounts.interfaces import TransactionType
from app.modules.capital_accounts.models.capital_account import CapitalAccountRecord
from app.modules.capital_accounts.services.capital_transaction import (
    CapitalTransactionService,
)

ZERO = Decimal("0")
BIZ_DATE = date(2026, 4, 10)


def _make_account(
    *,
    id: str = "acct-1",
    investor_id: str = "inv-1",
    ending_capital: Decimal = Decimal("1000000"),
    ownership_pct: Decimal = Decimal("1.0"),
    shares_held: Decimal = Decimal("10000"),
    share_class: str = "default",
    effective_date: date = BIZ_DATE,
) -> MagicMock:
    a = MagicMock(spec=CapitalAccountRecord)
    a.id = id
    a.investor_id = investor_id
    a.ending_capital = ending_capital
    a.ownership_pct = ownership_pct
    a.shares_held = shares_held
    a.share_class = share_class
    a.effective_date = effective_date
    return a


def _make_service(
    *,
    with_event_bus: bool = False,
    with_cash_service: bool = False,
) -> tuple:
    account_repo = AsyncMock()
    transaction_repo = AsyncMock()
    event_bus = AsyncMock() if with_event_bus else None
    cash_service = AsyncMock() if with_cash_service else None

    account_repo.insert = AsyncMock(side_effect=lambda rec, **kw: rec)
    transaction_repo.insert = AsyncMock()

    service = CapitalTransactionService(
        account_repo=account_repo,
        transaction_repo=transaction_repo,
        cash_service=cash_service,
        event_bus=event_bus,
    )
    return service, account_repo, transaction_repo, event_bus, cash_service


# ------------------------------------------------------------------
# allocate_daily — class_fees branch (lines 104-128)
# ------------------------------------------------------------------


class TestAllocateDailyClassFees:
    @pytest.mark.asyncio
    async def test_class_fees_allocates_per_class(self) -> None:
        """When class_fees is provided, fees are allocated per share class."""
        service, account_repo, transaction_repo, _, _ = _make_service()

        acct_a = _make_account(
            id="a1",
            investor_id="inv-1",
            ending_capital=Decimal("600000"),
            ownership_pct=Decimal("0.6"),
            share_class="A",
        )
        acct_b = _make_account(
            id="a2",
            investor_id="inv-2",
            ending_capital=Decimal("400000"),
            ownership_pct=Decimal("0.4"),
            share_class="B",
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct_a, acct_b])

        count = await service.allocate_daily(
            fund_pnl=Decimal("10000"),
            management_fee=ZERO,
            performance_fee=ZERO,
            nav_per_share=Decimal("105"),
            business_date=BIZ_DATE,
            class_fees={
                "A": (Decimal("300"), Decimal("600")),
                "B": (Decimal("200"), Decimal("400")),
            },
        )

        assert count == 2
        # Two accounts inserted
        assert account_repo.insert.call_count == 2

    @pytest.mark.asyncio
    async def test_class_fees_zero_total_capital_uses_fallback(self) -> None:
        """When class total capital is zero, cls_accounts is used as-is."""
        service, account_repo, _, _, _ = _make_service()

        acct = _make_account(
            id="a1",
            investor_id="inv-1",
            ending_capital=ZERO,
            ownership_pct=Decimal("1.0"),
            share_class="A",
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        count = await service.allocate_daily(
            fund_pnl=ZERO,
            management_fee=ZERO,
            performance_fee=ZERO,
            nav_per_share=Decimal("100"),
            business_date=BIZ_DATE,
            class_fees={"A": (Decimal("0"), Decimal("0"))},
        )

        assert count == 1

    @pytest.mark.asyncio
    async def test_class_fees_missing_class_uses_zero(self) -> None:
        """When a share class is not in class_fees dict, defaults to (0,0)."""
        service, account_repo, _, _, _ = _make_service()

        acct = _make_account(
            id="a1",
            investor_id="inv-1",
            ending_capital=Decimal("500000"),
            ownership_pct=Decimal("1.0"),
            share_class="C",
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        count = await service.allocate_daily(
            fund_pnl=Decimal("5000"),
            management_fee=ZERO,
            performance_fee=ZERO,
            nav_per_share=Decimal("100"),
            business_date=BIZ_DATE,
            class_fees={"A": (Decimal("100"), Decimal("200"))},
        )

        assert count == 1


# ------------------------------------------------------------------
# process_subscription — existing investor + cash service (lines 281, 333)
# ------------------------------------------------------------------


class TestSubscriptionExistingInvestor:
    @pytest.mark.asyncio
    async def test_subscription_adds_to_existing_account(self) -> None:
        service, account_repo, _, _, _ = _make_service()
        existing = _make_account(
            ending_capital=Decimal("500000"),
            shares_held=Decimal("5000"),
        )
        account_repo.get_latest_for_investor = AsyncMock(return_value=existing)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        result = await service.process_subscription(
            investor_id="inv-1",
            amount=Decimal("100000"),
            nav_per_share=Decimal("100"),
            business_date=BIZ_DATE,
        )

        # ending_capital should be existing + amount
        assert result.ending_capital == Decimal("600000")
        assert result.beginning_capital == Decimal("500000")
        assert result.contributions == Decimal("100000")

    @pytest.mark.asyncio
    async def test_subscription_credits_cash_service(self) -> None:
        service, account_repo, _, _, cash_service = _make_service(with_cash_service=True)
        account_repo.get_latest_for_investor = AsyncMock(return_value=None)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        portfolio_id = UUID("12345678-1234-1234-1234-123456789abc")

        await service.process_subscription(
            investor_id="inv-1",
            amount=Decimal("250000"),
            nav_per_share=Decimal("100"),
            business_date=BIZ_DATE,
            portfolio_id=portfolio_id,
            currency="EUR",
        )

        cash_service.credit.assert_called_once()
        call_kwargs = cash_service.credit.call_args.kwargs
        assert call_kwargs["portfolio_id"] == portfolio_id
        assert call_kwargs["currency"] == "EUR"
        assert call_kwargs["amount"] == Decimal("250000")


# ------------------------------------------------------------------
# process_redemption — edge cases (lines 399-400, 409, 447)
# ------------------------------------------------------------------


class TestRedemptionEdgeCases:
    @pytest.mark.asyncio
    async def test_redemption_no_existing_account_raises(self) -> None:
        service, account_repo, _, _, _ = _make_service()
        account_repo.get_latest_for_investor = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="No capital account found"):
            await service.process_redemption(
                investor_id="inv-1",
                amount=Decimal("100"),
                nav_per_share=Decimal("100"),
                business_date=BIZ_DATE,
            )

    @pytest.mark.asyncio
    async def test_redemption_zero_nav_per_share(self) -> None:
        """When nav_per_share is 0, shares_to_redeem should be ZERO."""
        service, account_repo, _, _, _ = _make_service()
        existing = _make_account(
            ending_capital=Decimal("100000"),
            shares_held=Decimal("1000"),
        )
        account_repo.get_latest_for_investor = AsyncMock(return_value=existing)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        result = await service.process_redemption(
            investor_id="inv-1",
            amount=Decimal("50000"),
            nav_per_share=ZERO,
            business_date=BIZ_DATE,
        )

        # shares_held should remain unchanged (1000 - 0)
        assert result.shares_held == Decimal("1000")

    @pytest.mark.asyncio
    async def test_redemption_debits_cash_service(self) -> None:
        service, account_repo, _, _, cash_service = _make_service(with_cash_service=True)
        existing = _make_account(ending_capital=Decimal("500000"))
        account_repo.get_latest_for_investor = AsyncMock(return_value=existing)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        portfolio_id = UUID("12345678-1234-1234-1234-123456789abc")

        await service.process_redemption(
            investor_id="inv-1",
            amount=Decimal("100000"),
            nav_per_share=Decimal("100"),
            business_date=BIZ_DATE,
            portfolio_id=portfolio_id,
            currency="GBP",
        )

        cash_service.debit.assert_called_once()
        call_kwargs = cash_service.debit.call_args.kwargs
        assert call_kwargs["portfolio_id"] == portfolio_id
        assert call_kwargs["currency"] == "GBP"
        assert call_kwargs["amount"] == Decimal("100000")

    @pytest.mark.asyncio
    async def test_redemption_clamps_negative_shares_to_zero(self) -> None:
        """When shares_to_redeem exceeds shares_held, new_shares is clamped to ZERO."""
        service, account_repo, _, _, _ = _make_service()
        existing = _make_account(
            ending_capital=Decimal("100000"),
            shares_held=Decimal("100"),  # Only 100 shares
        )
        account_repo.get_latest_for_investor = AsyncMock(return_value=existing)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        result = await service.process_redemption(
            investor_id="inv-1",
            amount=Decimal("50000"),
            nav_per_share=Decimal("1"),  # 50000 shares to redeem > 100 held
            business_date=BIZ_DATE,
        )

        assert result.shares_held == ZERO

    @pytest.mark.asyncio
    async def test_redemption_publishes_event_without_bus(self) -> None:
        """Redemption without event bus should not raise."""
        service, account_repo, _, _, _ = _make_service(with_event_bus=False)
        existing = _make_account(ending_capital=Decimal("500000"))
        account_repo.get_latest_for_investor = AsyncMock(return_value=existing)
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        result = await service.process_redemption(
            investor_id="inv-1",
            amount=Decimal("100000"),
            nav_per_share=Decimal("100"),
            business_date=BIZ_DATE,
        )

        assert result.ending_capital == Decimal("400000")


# ------------------------------------------------------------------
# _recompute_all_ownership (lines 499-506)
# ------------------------------------------------------------------


class TestRecomputeAllOwnership:
    @pytest.mark.asyncio
    async def test_recompute_empty_accounts(self) -> None:
        service, account_repo, _, _, _ = _make_service()
        account_repo.get_latest_by_fund = AsyncMock(return_value=[])

        # Should not raise
        await service._recompute_all_ownership(BIZ_DATE)

    @pytest.mark.asyncio
    async def test_recompute_updates_matching_date(self) -> None:
        service, account_repo, _, _, _ = _make_service()

        acct = _make_account(
            id="a1",
            ending_capital=Decimal("1000000"),
            effective_date=BIZ_DATE,
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        await service._recompute_all_ownership(BIZ_DATE)

        # Should have set ownership_pct on acct (since effective_date matches)
        assert acct.ownership_pct == Decimal("1")

    @pytest.mark.asyncio
    async def test_recompute_skips_non_matching_date(self) -> None:
        service, account_repo, _, _, _ = _make_service()

        acct = _make_account(
            id="a1",
            ending_capital=Decimal("1000000"),
            effective_date=date(2026, 4, 9),  # Different date
        )
        # Store original value
        original_pct = acct.ownership_pct
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        await service._recompute_all_ownership(BIZ_DATE)

        # ownership_pct should NOT have been updated (date doesn't match)
        assert acct.ownership_pct == original_pct


# ------------------------------------------------------------------
# allocate_daily — transaction records for non-zero amounts
# ------------------------------------------------------------------


class TestAllocateDailyTransactions:
    @pytest.mark.asyncio
    async def test_creates_pnl_and_fee_transactions(self) -> None:
        """When PnL and fees are non-zero, transaction records are created."""
        service, account_repo, transaction_repo, _, _ = _make_service()

        acct = _make_account(
            ending_capital=Decimal("1000000"),
            ownership_pct=Decimal("1.0"),
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        await service.allocate_daily(
            fund_pnl=Decimal("50000"),
            management_fee=Decimal("500"),
            performance_fee=Decimal("1000"),
            nav_per_share=Decimal("105"),
            business_date=BIZ_DATE,
        )

        # 1 PnL + 1 mgmt fee + 1 perf fee = 3 transaction inserts
        assert transaction_repo.insert.call_count == 3

    @pytest.mark.asyncio
    async def test_skips_zero_pnl_transaction(self) -> None:
        """When PnL is zero, no PnL transaction is created."""
        service, account_repo, transaction_repo, _, _ = _make_service()

        acct = _make_account(
            ending_capital=Decimal("1000000"),
            ownership_pct=Decimal("1.0"),
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        await service.allocate_daily(
            fund_pnl=ZERO,
            management_fee=Decimal("500"),
            performance_fee=Decimal("1000"),
            nav_per_share=Decimal("100"),
            business_date=BIZ_DATE,
        )

        # Only mgmt + perf fee transactions (no PnL)
        assert transaction_repo.insert.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_zero_fee_transactions(self) -> None:
        """When fees are zero, no fee transactions are created."""
        service, account_repo, transaction_repo, _, _ = _make_service()

        acct = _make_account(
            ending_capital=Decimal("1000000"),
            ownership_pct=Decimal("1.0"),
        )
        account_repo.get_latest_by_fund = AsyncMock(return_value=[acct])

        await service.allocate_daily(
            fund_pnl=Decimal("50000"),
            management_fee=ZERO,
            performance_fee=ZERO,
            nav_per_share=Decimal("105"),
            business_date=BIZ_DATE,
        )

        # Only PnL transaction
        assert transaction_repo.insert.call_count == 1
