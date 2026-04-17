"""Unit tests for fund_structures routes — direct async calls with mocked deps."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.fund_structures.interfaces import (
    BookRebalanceResult,
    FundOfFundsHolding,
    FundOfFundsNAV,
    MasterFeederLink,
    StrategyBook,
)
from app.modules.fund_structures.routes.fund_structure import (
    AddFoFHoldingRequest,
    CreateBookRequest,
    CreateMasterFeederRequest,
    RebalanceCheckRequest,
    UpdateBookRequest,
    UpdateHoldingNAVRequest,
    add_fof_holding,
    check_rebalance,
    compute_fof_nav,
    create_book,
    create_master_feeder_link,
    delete_book,
    get_book_tree,
    get_feeder_master,
    get_feeders_for_master,
    list_fof_holdings,
    update_book,
    update_holding_nav,
)

from datetime import UTC, datetime

NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_service() -> AsyncMock:
    return AsyncMock()


def _mock_session() -> AsyncMock:
    return AsyncMock()


def _mock_ctx(fund_slug: str = "alpha") -> MagicMock:
    ctx = MagicMock()
    ctx.fund_slug = fund_slug
    return ctx


def _mf_link(**overrides) -> MasterFeederLink:
    defaults = dict(
        id=uuid4(),
        master_fund_slug="alpha",
        feeder_fund_slug="beta",
        allocation_pct=Decimal("0.40"),
        is_active=True,
        created_at=NOW,
    )
    defaults.update(overrides)
    return MasterFeederLink(**defaults)


def _strategy_book(**overrides) -> StrategyBook:
    defaults = dict(
        id=uuid4(),
        fund_slug="alpha",
        name="Equity",
        level="strategy",
        parent_id=None,
        portfolio_id=None,
        target_allocation_pct=Decimal("0.6"),
        actual_allocation_pct=None,
        is_active=True,
    )
    defaults.update(overrides)
    return StrategyBook(**defaults)


def _fof_holding(**overrides) -> FundOfFundsHolding:
    defaults = dict(
        id=uuid4(),
        fof_fund_slug="fof-alpha",
        underlying_fund_slug="fund-b",
        underlying_fund_name="Fund B",
        allocation_pct=Decimal("0.3"),
        current_nav=Decimal("500000"),
        is_internal=True,
    )
    defaults.update(overrides)
    return FundOfFundsHolding(**defaults)


# ---------------------------------------------------------------------------
# Master-Feeder routes
# ---------------------------------------------------------------------------


class TestCreateMasterFeederLink:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self) -> None:
        svc = _mock_service()
        link = _mf_link()
        svc.create_master_feeder_link.return_value = link
        body = CreateMasterFeederRequest(
            master_fund_slug="alpha",
            feeder_fund_slug="beta",
            allocation_pct=Decimal("0.40"),
        )
        session = _mock_session()

        result = await create_master_feeder_link(
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is link
        svc.create_master_feeder_link.assert_awaited_once_with(
            "alpha", "beta", Decimal("0.40"), session=session,
        )


class TestGetFeedersForMaster:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        svc = _mock_service()
        links = [_mf_link(feeder_fund_slug="beta"), _mf_link(feeder_fund_slug="gamma")]
        svc.get_feeder_structure.return_value = links
        session = _mock_session()

        result = await get_feeders_for_master(
            master_slug="alpha",
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result == links
        svc.get_feeder_structure.assert_awaited_once_with("alpha", session=session)


class TestGetFeederMaster:
    @pytest.mark.asyncio
    async def test_returns_link_when_found(self) -> None:
        svc = _mock_service()
        link = _mf_link(master_fund_slug="alpha", feeder_fund_slug="beta")
        svc.get_master_for_feeder.return_value = link
        session = _mock_session()

        result = await get_feeder_master(
            feeder_slug="beta",
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is link
        svc.get_master_for_feeder.assert_awaited_once_with("beta", session=session)

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        svc = _mock_service()
        svc.get_master_for_feeder.return_value = None
        session = _mock_session()

        result = await get_feeder_master(
            feeder_slug="standalone",
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is None


# ---------------------------------------------------------------------------
# Strategy Book routes
# ---------------------------------------------------------------------------


class TestCreateBook:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self) -> None:
        svc = _mock_service()
        book = _strategy_book()
        svc.create_book.return_value = book
        parent_id = uuid4()
        portfolio_id = uuid4()
        body = CreateBookRequest(
            fund_slug="alpha",
            name="Equity",
            level="strategy",
            parent_id=parent_id,
            portfolio_id=portfolio_id,
            target_allocation_pct=Decimal("0.6"),
        )
        session = _mock_session()

        result = await create_book(
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is book
        svc.create_book.assert_awaited_once_with(
            "alpha",
            "Equity",
            "strategy",
            parent_id=str(parent_id),
            portfolio_id=str(portfolio_id),
            target_pct=Decimal("0.6"),
            session=session,
        )

    @pytest.mark.asyncio
    async def test_none_parent_and_portfolio(self) -> None:
        svc = _mock_service()
        book = _strategy_book()
        svc.create_book.return_value = book
        body = CreateBookRequest(
            fund_slug="alpha",
            name="Top",
            level="fund",
        )
        session = _mock_session()

        await create_book(
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        svc.create_book.assert_awaited_once_with(
            "alpha", "Top", "fund",
            parent_id=None,
            portfolio_id=None,
            target_pct=Decimal("1.0"),
            session=session,
        )


class TestGetBookTree:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        svc = _mock_service()
        books = [_strategy_book(name="A"), _strategy_book(name="B")]
        svc.get_book_tree.return_value = books
        session = _mock_session()

        result = await get_book_tree(
            fund_slug="alpha",
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result == books


class TestUpdateBook:
    @pytest.mark.asyncio
    async def test_returns_updated_book(self) -> None:
        svc = _mock_service()
        updated = _strategy_book(name="Updated", target_allocation_pct=Decimal("0.7"))
        svc.update_book.return_value = updated
        book_id = uuid4()
        body = UpdateBookRequest(name="Updated", target_allocation_pct=Decimal("0.7"))
        session = _mock_session()

        result = await update_book(
            book_id=book_id,
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is updated
        svc.update_book.assert_awaited_once_with(
            str(book_id),
            name="Updated",
            target_pct=Decimal("0.7"),
            session=session,
        )

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        svc = _mock_service()
        svc.update_book.return_value = None
        body = UpdateBookRequest(name="X")
        session = _mock_session()

        result = await update_book(
            book_id=uuid4(),
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is None


class TestDeleteBook:
    @pytest.mark.asyncio
    async def test_delegates_to_repo(self) -> None:
        svc = _mock_service()
        book_id = uuid4()
        session = _mock_session()

        await delete_book(
            book_id=book_id,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        svc.delete_book.assert_awaited_once_with(str(book_id), session=session)


class TestCheckRebalance:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self) -> None:
        svc = _mock_service()
        book_id = uuid4()
        results = [
            BookRebalanceResult(
                book_id=book_id,
                book_name="Equity",
                target_pct=Decimal("0.6"),
                current_pct=Decimal("0.7"),
                drift_pct=Decimal("0.1"),
                suggested_trade_amount=Decimal("100000"),
            )
        ]
        svc.check_rebalance.return_value = results
        body = RebalanceCheckRequest(book_navs={book_id: Decimal("700000")})
        session = _mock_session()

        result = await check_rebalance(
            fund_slug="alpha",
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result == results


# ---------------------------------------------------------------------------
# Fund of Funds routes
# ---------------------------------------------------------------------------


class TestAddFoFHolding:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self) -> None:
        svc = _mock_service()
        holding = _fof_holding()
        svc.add_fof_holding.return_value = holding
        body = AddFoFHoldingRequest(
            fof_fund_slug="fof-alpha",
            underlying_fund_name="Fund B",
            allocation_pct=Decimal("0.3"),
            underlying_fund_slug="fund-b",
            is_internal=True,
        )
        session = _mock_session()

        result = await add_fof_holding(
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is holding
        svc.add_fof_holding.assert_awaited_once_with(
            "fof-alpha",
            "Fund B",
            Decimal("0.3"),
            underlying_slug="fund-b",
            is_internal=True,
            session=session,
        )


class TestListFoFHoldings:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        svc = _mock_service()
        holdings = [_fof_holding(), _fof_holding()]
        svc.get_fof_holdings.return_value = holdings
        session = _mock_session()

        result = await list_fof_holdings(
            fof_slug="fof-alpha",
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result == holdings


class TestComputeFoFNAV:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self) -> None:
        svc = _mock_service()
        nav = FundOfFundsNAV(
            fof_fund_slug="fof-alpha",
            total_nav=Decimal("1000000"),
            holdings=[],
            computed_at=NOW,
        )
        svc.compute_fof_nav.return_value = nav
        session = _mock_session()

        result = await compute_fof_nav(
            fof_slug="fof-alpha",
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        assert result is nav


class TestUpdateHoldingNAV:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self) -> None:
        svc = _mock_service()
        holding_id = uuid4()
        body = UpdateHoldingNAVRequest(nav=Decimal("999999"))
        session = _mock_session()

        await update_holding_nav(
            holding_id=holding_id,
            body=body,
            request_context=_mock_ctx(),
            service=svc,
            session=session,
        )

        svc.update_holding_nav.assert_awaited_once_with(
            str(holding_id), Decimal("999999"), session=session,
        )
