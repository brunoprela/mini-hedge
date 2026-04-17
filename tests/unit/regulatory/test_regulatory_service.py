"""Unit tests for RegulatoryService — form PF, 13F, investor statements, performance letters."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.regulatory.interfaces import FormPFFrequency
from app.modules.regulatory.services.regulatory import RegulatoryService
from app.shared.audit.events import AuditEventType

_FUND = "alpha"
_DATE = date(2026, 3, 31)


def _stamp(record, **_kw):
    """Simulate DB default columns on save."""
    return record


def _make_service(
    *,
    capital_overview: MagicMock | None = None,
    counterparties: list | None = None,
    positions: list | None = None,
    investor_history: list | None = None,
    event_bus: AsyncMock | None = None,
) -> RegulatoryService:
    filing_repo = AsyncMock()
    filing_repo.insert = AsyncMock(side_effect=_stamp)
    filing_repo.list_all = AsyncMock(return_value=[])

    statement_repo = AsyncMock()
    statement_repo.insert = AsyncMock(side_effect=_stamp)

    letter_repo = AsyncMock()
    letter_repo.insert = AsyncMock(side_effect=_stamp)

    position_service = AsyncMock()
    position_service.get_positions = AsyncMock(return_value=positions or [])

    capital_service = None
    if capital_overview is not None:
        capital_service = AsyncMock()
        capital_service.get_fund_overview = AsyncMock(return_value=capital_overview)
        capital_service.get_investor_history = AsyncMock(return_value=investor_history or [])

    risk_service = None
    if counterparties is not None:
        risk_service = AsyncMock()
        risk_service.list_counterparties = AsyncMock(return_value=counterparties)

    return RegulatoryService(
        filing_repo=filing_repo,
        statement_repo=statement_repo,
        letter_repo=letter_repo,
        position_service=position_service,
        capital_service=capital_service,
        risk_service=risk_service,
        event_bus=event_bus,
    )


def _make_overview(
    aum: Decimal = Decimal("50000000"),
    investors: int = 12,
    shares: Decimal = Decimal("50000"),
) -> MagicMock:
    o = MagicMock()
    o.total_aum = aum
    o.total_investors = investors
    o.total_shares_outstanding = shares
    return o


def _make_counterparty(name: str, cpty_type: str, limit: Decimal) -> MagicMock:
    c = MagicMock()
    c.name = name
    c.counterparty_type = cpty_type
    c.credit_limit = limit
    return c


def _make_position(instrument_id: str, quantity: Decimal, market_value: Decimal) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.quantity = quantity
    p.market_value = market_value
    return p


def _make_account(
    *,
    effective_date: date,
    investor_name: str = "Test Investor",
    share_class: str = "default",
    beginning_capital: Decimal = Decimal("1000000"),
    ending_capital: Decimal = Decimal("1050000"),
    contributions: Decimal = Decimal("0"),
    withdrawals: Decimal = Decimal("0"),
    management_fee_allocation: Decimal = Decimal("1000"),
    performance_fee_allocation: Decimal = Decimal("2000"),
    pnl_allocation: Decimal = Decimal("53000"),
    ownership_pct: Decimal = Decimal("0.10"),
    shares_held: Decimal = Decimal("10000"),
) -> MagicMock:
    a = MagicMock()
    a.effective_date = effective_date
    a.investor_name = investor_name
    a.share_class = share_class
    a.beginning_capital = beginning_capital
    a.ending_capital = ending_capital
    a.contributions = contributions
    a.withdrawals = withdrawals
    a.management_fee_allocation = management_fee_allocation
    a.performance_fee_allocation = performance_fee_allocation
    a.pnl_allocation = pnl_allocation
    a.ownership_pct = ownership_pct
    a.shares_held = shares_held
    return a


# ------------------------------------------------------------------
# Form PF
# ------------------------------------------------------------------


class TestGenerateFormPF:
    @pytest.mark.asyncio
    async def test_generates_form_pf_with_capital_data(self) -> None:
        overview = _make_overview()
        svc = _make_service(capital_overview=overview)

        result = await svc.generate_form_pf(_FUND, _DATE, fund_name="Alpha Fund")

        assert result.fund_slug == _FUND
        assert result.fund_name == "Alpha Fund"
        assert result.net_asset_value == Decimal("50000000")
        assert result.total_investors == 12
        assert result.reporting_period_end == _DATE

    @pytest.mark.asyncio
    async def test_generates_form_pf_without_capital(self) -> None:
        svc = _make_service()

        result = await svc.generate_form_pf(_FUND, _DATE)

        assert result.net_asset_value == Decimal("0")
        assert result.total_investors == 0
        assert result.fund_name == _FUND  # falls back to slug

    @pytest.mark.asyncio
    async def test_form_pf_includes_counterparties(self) -> None:
        overview = _make_overview()
        cptys = [
            _make_counterparty("GS", "prime_broker", Decimal("10000000")),
            _make_counterparty("MS", "prime_broker", Decimal("8000000")),
        ]
        svc = _make_service(capital_overview=overview, counterparties=cptys)

        result = await svc.generate_form_pf(_FUND, _DATE)

        assert len(result.top_counterparties) == 2
        assert result.top_counterparties[0]["name"] == "GS"

    @pytest.mark.asyncio
    async def test_form_pf_persists_filing(self) -> None:
        svc = _make_service()
        await svc.generate_form_pf(_FUND, _DATE)

        svc._filing_repo.insert.assert_called_once()
        saved = svc._filing_repo.insert.call_args.args[0]
        assert saved.filing_type == "form_pf"
        assert saved.status == "draft"

    @pytest.mark.asyncio
    async def test_form_pf_publishes_event(self) -> None:
        event_bus = AsyncMock()
        svc = _make_service(event_bus=event_bus)

        await svc.generate_form_pf(_FUND, _DATE)

        event_bus.publish.assert_called_once()
        _, event = event_bus.publish.call_args.args
        assert event.event_type == AuditEventType.FORM_PF_GENERATED
        assert event.data["fund_slug"] == _FUND

    @pytest.mark.asyncio
    async def test_form_pf_no_event_without_bus(self) -> None:
        svc = _make_service(event_bus=None)
        result = await svc.generate_form_pf(_FUND, _DATE)
        assert result is not None  # completes without error

    @pytest.mark.asyncio
    async def test_form_pf_counterparty_exception_swallowed(self) -> None:
        """When risk_service.list_counterparties raises, the exception is caught."""
        overview = _make_overview()
        risk_service = AsyncMock()
        risk_service.list_counterparties = AsyncMock(side_effect=RuntimeError("boom"))

        svc = _make_service(capital_overview=overview, counterparties=[])
        svc._risk = risk_service  # override with the failing one

        result = await svc.generate_form_pf(_FUND, _DATE)

        assert result is not None
        assert result.top_counterparties == []


# ------------------------------------------------------------------
# 13F
# ------------------------------------------------------------------


class TestGenerate13F:
    @pytest.mark.asyncio
    async def test_generates_13f_with_positions(self) -> None:
        positions = [
            _make_position("00000000-0000-0000-0000-000000000aaa", Decimal("1000"), Decimal("150000")),
            _make_position("00000000-0000-0000-0000-000000000bbb", Decimal("500"), Decimal("200000")),
        ]
        sec_master = AsyncMock()
        instrument = MagicMock()
        instrument.asset_class = "equity"
        instrument.cusip = "037833100"
        instrument.name = "Apple Inc."
        sec_master.get_by_id = AsyncMock(return_value=instrument)

        svc = _make_service(positions=positions)
        svc._sec_master = sec_master

        result = await svc.generate_13f(
            _FUND, _DATE, portfolio_ids=["00000000-0000-0000-0000-000000000001"]
        )

        assert result.total_positions == 2
        assert len(result.entries) == 2
        assert result.entries[0].issuer_name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_13f_skips_non_equity(self) -> None:
        positions = [_make_position("00000000-0000-0000-0000-000000000ccc", Decimal("100"), Decimal("100000"))]
        sec_master = AsyncMock()
        instrument = MagicMock()
        instrument.asset_class = "fixed_income"
        instrument.cusip = None
        instrument.name = "US Treasury"
        sec_master.get_by_id = AsyncMock(return_value=instrument)

        svc = _make_service(positions=positions)
        svc._sec_master = sec_master

        result = await svc.generate_13f(
            _FUND, _DATE, portfolio_ids=["00000000-0000-0000-0000-000000000001"]
        )

        assert result.total_positions == 0
        assert len(result.entries) == 0

    @pytest.mark.asyncio
    async def test_13f_empty_without_portfolios(self) -> None:
        svc = _make_service()

        result = await svc.generate_13f(_FUND, _DATE)

        assert result.total_positions == 0

    @pytest.mark.asyncio
    async def test_13f_persists_filing(self) -> None:
        svc = _make_service()
        await svc.generate_13f(_FUND, _DATE)

        svc._filing_repo.insert.assert_called_once()
        saved = svc._filing_repo.insert.call_args.args[0]
        assert saved.filing_type == "13f"

    @pytest.mark.asyncio
    async def test_13f_publishes_event(self) -> None:
        event_bus = AsyncMock()
        svc = _make_service(event_bus=event_bus)

        await svc.generate_13f(_FUND, _DATE)

        event_bus.publish.assert_called_once()
        _, event = event_bus.publish.call_args.args
        assert event.event_type == AuditEventType.FILING_13F_GENERATED
        assert event.data["fund_slug"] == _FUND


# ------------------------------------------------------------------
# Investor Statement
# ------------------------------------------------------------------


class TestGenerateInvestorStatement:
    @pytest.mark.asyncio
    async def test_generates_statement(self) -> None:
        overview = _make_overview()
        history = [
            _make_account(effective_date=date(2026, 3, 31)),
            _make_account(
                effective_date=date(2026, 1, 31),
                beginning_capital=Decimal("1000000"),
                ending_capital=Decimal("1010000"),
            ),
        ]
        svc = _make_service(capital_overview=overview, investor_history=history)

        result = await svc.generate_investor_statement(
            "00000000-0000-0000-0000-000000000010",
            date(2026, 1, 1),
            date(2026, 3, 31),
        )

        assert result is not None
        assert result.investor_name == "Test Investor"
        assert result.beginning_capital == Decimal("1000000")
        assert result.ending_capital == Decimal("1050000")

    @pytest.mark.asyncio
    async def test_returns_none_without_capital_service(self) -> None:
        svc = _make_service()

        result = await svc.generate_investor_statement(
            "00000000-0000-0000-0000-000000000010",
            date(2026, 1, 1),
            date(2026, 3, 31),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_without_history(self) -> None:
        overview = _make_overview()
        svc = _make_service(capital_overview=overview, investor_history=[])

        result = await svc.generate_investor_statement(
            "00000000-0000-0000-0000-000000000010",
            date(2026, 1, 1),
            date(2026, 3, 31),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_accounts_in_period(self) -> None:
        overview = _make_overview()
        # Account outside the requested period
        history = [_make_account(effective_date=date(2025, 12, 31))]
        svc = _make_service(capital_overview=overview, investor_history=history)

        result = await svc.generate_investor_statement(
            "00000000-0000-0000-0000-000000000010",
            date(2026, 1, 1),
            date(2026, 3, 31),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_statement_persists_record(self) -> None:
        overview = _make_overview()
        history = [_make_account(effective_date=date(2026, 3, 31))]
        svc = _make_service(capital_overview=overview, investor_history=history)

        await svc.generate_investor_statement(
            "00000000-0000-0000-0000-000000000010",
            date(2026, 1, 1),
            date(2026, 3, 31),
        )

        svc._statement_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_statement_publishes_event(self) -> None:
        event_bus = AsyncMock()
        overview = _make_overview()
        history = [_make_account(effective_date=date(2026, 3, 31))]
        svc = _make_service(capital_overview=overview, investor_history=history, event_bus=event_bus)

        await svc.generate_investor_statement(
            "00000000-0000-0000-0000-000000000010",
            date(2026, 1, 1),
            date(2026, 3, 31),
        )

        event_bus.publish.assert_called_once()
        _, event = event_bus.publish.call_args.args
        assert event.event_type == AuditEventType.INVESTOR_STATEMENT_GENERATED
        assert event.data["investor_id"] == "00000000-0000-0000-0000-000000000010"


# ------------------------------------------------------------------
# Performance Letter
# ------------------------------------------------------------------


class TestGeneratePerformanceLetter:
    @pytest.mark.asyncio
    async def test_generates_letter_with_capital(self) -> None:
        overview = _make_overview()
        svc = _make_service(capital_overview=overview)

        result = await svc.generate_performance_letter(_FUND, _DATE, fund_name="Alpha Fund")

        assert result.fund_name == "Alpha Fund"
        assert result.total_aum == Decimal("50000000")
        assert result.total_investors == 12
        assert result.nav_per_share == Decimal("1000.0000")  # 50M / 50K shares

    @pytest.mark.asyncio
    async def test_generates_letter_without_capital(self) -> None:
        svc = _make_service()

        result = await svc.generate_performance_letter(_FUND, _DATE)

        assert result.total_aum == Decimal("0")
        assert result.nav_per_share == Decimal("0")

    @pytest.mark.asyncio
    async def test_letter_persists_record(self) -> None:
        svc = _make_service()
        await svc.generate_performance_letter(_FUND, _DATE)

        svc._letter_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_letter_publishes_event(self) -> None:
        event_bus = AsyncMock()
        svc = _make_service(event_bus=event_bus)

        await svc.generate_performance_letter(_FUND, _DATE)

        event_bus.publish.assert_called_once()
        _, event = event_bus.publish.call_args.args
        assert event.event_type == AuditEventType.PERFORMANCE_LETTER_GENERATED
        assert event.data["fund_slug"] == _FUND


# ------------------------------------------------------------------
# Queries
# ------------------------------------------------------------------


class TestListFilings:
    @pytest.mark.asyncio
    async def test_list_filings(self) -> None:
        record = MagicMock()
        record.id = "00000000-0000-0000-0000-000000000001"
        record.filing_type = "form_pf"
        record.reporting_period = _DATE
        record.status = "draft"
        record.generated_at = datetime(2026, 3, 31, 12, 0, tzinfo=timezone.utc)

        svc = _make_service()
        svc._filing_repo.list_all = AsyncMock(return_value=[record])

        result = await svc.list_filings(filing_type="form_pf")

        assert len(result) == 1
        assert result[0]["filing_type"] == "form_pf"
        assert result[0]["id"] == "00000000-0000-0000-0000-000000000001"

    @pytest.mark.asyncio
    async def test_list_filings_empty(self) -> None:
        svc = _make_service()
        result = await svc.list_filings()
        assert result == []
