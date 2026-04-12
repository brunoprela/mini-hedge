"""Unit tests for CapitalAccountService — read-only queries on investor capital accounts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.capital_accounts.services.capital_account import CapitalAccountService

_INV_ID = "00000000-0000-0000-0000-000000000010"
_INV2_ID = "00000000-0000-0000-0000-000000000020"
_ACCT_ID = "00000000-0000-0000-0000-000000000001"
_ACCT2_ID = "00000000-0000-0000-0000-000000000002"
_TXN_ID = "00000000-0000-0000-0000-000000000099"


def _make_investor(inv_id: str = _INV_ID, name: str = "Test Investor") -> MagicMock:
    r = MagicMock()
    r.id = inv_id
    r.name = name
    r.entity_type = "institution"
    r.tax_jurisdiction = "US"
    r.contact_email = "test@fund.com"
    r.is_active = True
    return r


def _make_account(
    acct_id: str = _ACCT_ID,
    investor_id: str = _INV_ID,
    *,
    ending_capital: Decimal = Decimal("5000000"),
    shares_held: Decimal = Decimal("5000"),
    ownership_pct: Decimal = Decimal("0.50"),
    share_class: str = "default",
    effective_date: date = date(2026, 3, 31),
) -> MagicMock:
    a = MagicMock()
    a.id = acct_id
    a.investor_id = investor_id
    a.share_class = share_class
    a.beginning_capital = Decimal("4800000")
    a.contributions = Decimal("0")
    a.withdrawals = Decimal("0")
    a.pnl_allocation = Decimal("200000")
    a.management_fee_allocation = Decimal("5000")
    a.performance_fee_allocation = Decimal("10000")
    a.ending_capital = ending_capital
    a.ownership_pct = ownership_pct
    a.shares_held = shares_held
    a.effective_date = effective_date
    return a


def _make_txn() -> MagicMock:
    t = MagicMock()
    t.id = _TXN_ID
    t.capital_account_id = _ACCT_ID
    t.transaction_type = "subscription"
    t.amount = Decimal("1000000")
    t.shares = Decimal("1000")
    t.nav_per_share = Decimal("1000")
    t.business_date = date(2026, 1, 15)
    t.notes = "Initial subscription"
    t.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    return t


def _make_service(
    *,
    investors: list | None = None,
    accounts: list | None = None,
    accounts_by_class: list | None = None,
    investor_accounts: list | None = None,
    transactions: list | None = None,
    investor_lookup: MagicMock | None = None,
    total_shares: Decimal = Decimal("10000"),
) -> CapitalAccountService:
    investor_repo = AsyncMock()
    investor_repo.get_all_active = AsyncMock(return_value=investors or [])
    investor_repo.get_by_id = AsyncMock(return_value=investor_lookup)

    account_repo = AsyncMock()
    account_repo.get_latest_by_fund = AsyncMock(return_value=accounts or [])
    account_repo.get_latest_by_share_class = AsyncMock(return_value=accounts_by_class or [])
    account_repo.get_by_investor = AsyncMock(return_value=investor_accounts or [])
    account_repo.get_total_shares = AsyncMock(return_value=total_shares)

    transaction_repo = AsyncMock()
    transaction_repo.get_by_investor = AsyncMock(return_value=transactions or [])

    return CapitalAccountService(
        investor_repo=investor_repo,
        account_repo=account_repo,
        transaction_repo=transaction_repo,
    )


# ------------------------------------------------------------------
# list_investors
# ------------------------------------------------------------------


class TestListInvestors:
    @pytest.mark.asyncio
    async def test_returns_investor_info(self) -> None:
        inv = _make_investor()
        svc = _make_service(investors=[inv])

        result = await svc.list_investors()

        assert len(result) == 1
        assert result[0].id == UUID(_INV_ID)
        assert result[0].name == "Test Investor"
        assert result[0].entity_type == "institution"

    @pytest.mark.asyncio
    async def test_empty_when_no_investors(self) -> None:
        svc = _make_service()
        assert await svc.list_investors() == []


# ------------------------------------------------------------------
# get_capital_accounts
# ------------------------------------------------------------------


class TestGetCapitalAccounts:
    @pytest.mark.asyncio
    async def test_returns_accounts_with_investor_names(self) -> None:
        inv = _make_investor()
        acct = _make_account()
        svc = _make_service(investors=[inv], accounts=[acct])

        result = await svc.get_capital_accounts()

        assert len(result) == 1
        assert result[0].investor_name == "Test Investor"
        assert result[0].ending_capital == Decimal("5000000")

    @pytest.mark.asyncio
    async def test_unknown_investor_name_fallback(self) -> None:
        # Account exists but investor not in active list
        acct = _make_account(investor_id="00000000-0000-0000-0000-000000000099")
        svc = _make_service(accounts=[acct])

        result = await svc.get_capital_accounts()

        assert result[0].investor_name == "Unknown"


# ------------------------------------------------------------------
# get_investor_history
# ------------------------------------------------------------------


class TestGetInvestorHistory:
    @pytest.mark.asyncio
    async def test_returns_history(self) -> None:
        inv = _make_investor()
        accts = [
            _make_account(effective_date=date(2026, 3, 31)),
            _make_account(acct_id=_ACCT2_ID, effective_date=date(2026, 2, 28)),
        ]
        svc = _make_service(investor_lookup=inv, investor_accounts=accts)

        result = await svc.get_investor_history(_INV_ID)

        assert len(result) == 2
        assert result[0].investor_name == "Test Investor"

    @pytest.mark.asyncio
    async def test_unknown_name_when_investor_missing(self) -> None:
        accts = [_make_account()]
        svc = _make_service(investor_lookup=None, investor_accounts=accts)

        result = await svc.get_investor_history(_INV_ID)

        assert result[0].investor_name == "Unknown"

    @pytest.mark.asyncio
    async def test_passes_date_filters(self) -> None:
        svc = _make_service(investor_lookup=_make_investor())

        await svc.get_investor_history(
            _INV_ID, from_date=date(2026, 1, 1), to_date=date(2026, 3, 31)
        )

        svc._account_repo.get_by_investor.assert_called_once_with(
            _INV_ID, from_date=date(2026, 1, 1), to_date=date(2026, 3, 31), session=None
        )


# ------------------------------------------------------------------
# get_transactions
# ------------------------------------------------------------------


class TestGetTransactions:
    @pytest.mark.asyncio
    async def test_returns_transactions(self) -> None:
        txn = _make_txn()
        svc = _make_service(transactions=[txn])

        result = await svc.get_transactions(_INV_ID)

        assert len(result) == 1
        assert result[0].id == UUID(_TXN_ID)
        assert result[0].amount == Decimal("1000000")
        assert result[0].transaction_type == "subscription"

    @pytest.mark.asyncio
    async def test_empty_transactions(self) -> None:
        svc = _make_service()
        assert await svc.get_transactions(_INV_ID) == []


# ------------------------------------------------------------------
# get_fund_overview
# ------------------------------------------------------------------


class TestGetFundOverview:
    @pytest.mark.asyncio
    async def test_returns_overview(self) -> None:
        accts = [
            _make_account(ending_capital=Decimal("5000000"), shares_held=Decimal("5000"), ownership_pct=Decimal("0.50")),
            _make_account(
                acct_id=_ACCT2_ID,
                investor_id=_INV2_ID,
                ending_capital=Decimal("5000000"),
                shares_held=Decimal("5000"),
                ownership_pct=Decimal("0.50"),
            ),
        ]
        svc = _make_service(accounts=accts)

        result = await svc.get_fund_overview()

        assert result.total_aum == Decimal("10000000")
        assert result.total_investors == 2
        assert result.total_shares_outstanding == Decimal("10000")
        assert result.largest_investor_pct == Decimal("0.50")

    @pytest.mark.asyncio
    async def test_empty_fund_overview(self) -> None:
        svc = _make_service(accounts=[])

        result = await svc.get_fund_overview()

        assert result.total_aum == Decimal("0")
        assert result.total_investors == 0
        assert result.total_shares_outstanding == Decimal("0")


# ------------------------------------------------------------------
# get_share_class_nav
# ------------------------------------------------------------------


class TestGetShareClassNav:
    @pytest.mark.asyncio
    async def test_computes_nav_per_share(self) -> None:
        accts = [
            _make_account(ending_capital=Decimal("5000000"), shares_held=Decimal("5000")),
        ]
        svc = _make_service(accounts_by_class=accts)

        aum, shares, nav = await svc.get_share_class_nav("default")

        assert aum == Decimal("5000000")
        assert shares == Decimal("5000")
        assert nav == Decimal("1000")

    @pytest.mark.asyncio
    async def test_zero_shares_returns_zero_nav(self) -> None:
        svc = _make_service(accounts_by_class=[])

        aum, shares, nav = await svc.get_share_class_nav("default")

        assert aum == Decimal("0")
        assert nav == Decimal("0")


# ------------------------------------------------------------------
# list_share_classes
# ------------------------------------------------------------------


class TestListShareClasses:
    @pytest.mark.asyncio
    async def test_returns_sorted_classes(self) -> None:
        accts = [
            _make_account(share_class="institutional"),
            _make_account(acct_id=_ACCT2_ID, share_class="default"),
        ]
        svc = _make_service(accounts=accts)

        result = await svc.list_share_classes()

        assert result == ["default", "institutional"]

    @pytest.mark.asyncio
    async def test_empty_when_no_accounts(self) -> None:
        svc = _make_service()
        assert await svc.list_share_classes() == []


# ------------------------------------------------------------------
# get_share_class_investor_count
# ------------------------------------------------------------------


class TestGetShareClassInvestorCount:
    @pytest.mark.asyncio
    async def test_counts_investors(self) -> None:
        accts = [_make_account(), _make_account(acct_id=_ACCT2_ID, investor_id=_INV2_ID)]
        svc = _make_service(accounts_by_class=accts)

        count = await svc.get_share_class_investor_count("default")

        assert count == 2


# ------------------------------------------------------------------
# get_total_shares
# ------------------------------------------------------------------


class TestGetTotalShares:
    @pytest.mark.asyncio
    async def test_delegates_to_repo(self) -> None:
        svc = _make_service(total_shares=Decimal("50000"))

        result = await svc.get_total_shares()

        assert result == Decimal("50000")
