"""Unit tests for FundStructuresService — mocked repos, real event bus."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.fund_structures.models import (
    FundOfFundsHoldingRecord,
    MasterFeederLinkRecord,
    StrategyBookRecord,
)
from app.modules.fund_structures.service import FundStructuresService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)

AUDIT_TOPIC = "shared.audit"


def _stamp_mf_link(record: MasterFeederLinkRecord) -> None:
    """Simulate DB defaults on a freshly constructed MasterFeederLinkRecord."""
    if record.id is None:
        record.id = str(uuid4())
    if record.is_active is None:
        record.is_active = True
    if record.created_at is None:
        record.created_at = NOW


def _stamp_strategy_book(record: StrategyBookRecord) -> None:
    """Simulate DB defaults on a freshly constructed StrategyBookRecord."""
    if record.id is None:
        record.id = str(uuid4())
    if record.is_active is None:
        record.is_active = True
    if record.created_at is None:
        record.created_at = NOW


def _stamp_fof_holding(record: FundOfFundsHoldingRecord) -> None:
    """Simulate DB defaults on a freshly constructed FundOfFundsHoldingRecord."""
    if record.id is None:
        record.id = str(uuid4())
    if record.is_internal is None:
        record.is_internal = False
    if record.is_active is None:
        record.is_active = True
    if record.current_nav is None:
        record.current_nav = Decimal("0")
    if record.created_at is None:
        record.created_at = NOW


def _make_mf_link_record(**overrides) -> MagicMock:
    defaults = dict(
        id=str(uuid4()),
        master_fund_slug="master-alpha",
        feeder_fund_slug="feeder-a",
        allocation_pct=Decimal("0.4"),
        is_active=True,
        created_at=NOW,
    )
    defaults.update(overrides)
    record = MagicMock(spec=MasterFeederLinkRecord)
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _make_strategy_book_record(**overrides) -> MagicMock:
    defaults = dict(
        id=str(uuid4()),
        fund_slug="alpha",
        name="Equity Book",
        level="strategy",
        parent_id=None,
        portfolio_id=None,
        target_allocation_pct=Decimal("0.6"),
        is_active=True,
        created_at=NOW,
    )
    defaults.update(overrides)
    record = MagicMock(spec=StrategyBookRecord)
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _make_fof_holding_record(**overrides) -> MagicMock:
    defaults = dict(
        id=str(uuid4()),
        fof_fund_slug="fof-alpha",
        underlying_fund_slug="fund-b",
        underlying_fund_name="Fund B",
        allocation_pct=Decimal("0.3"),
        current_nav=Decimal("500000.00"),
        is_internal=True,
        is_active=True,
        created_at=NOW,
    )
    defaults.update(overrides)
    record = MagicMock(spec=FundOfFundsHoldingRecord)
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(event_bus, [AUDIT_TOPIC])
    return cap


@pytest.fixture
def mf_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def sb_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fof_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_session_factory() -> MagicMock:
    sf = MagicMock()
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm
    return sf


@pytest.fixture
def service(
    mf_repo: AsyncMock,
    sb_repo: AsyncMock,
    fof_repo: AsyncMock,
    mock_session_factory: MagicMock,
    event_bus: InProcessEventBus,
) -> FundStructuresService:
    return FundStructuresService(
        master_feeder_repo=mf_repo,
        strategy_book_repo=sb_repo,
        fof_repo=fof_repo,
        session_factory=mock_session_factory,
        event_bus=event_bus,
    )


@pytest.fixture
def service_no_bus(
    mf_repo: AsyncMock,
    sb_repo: AsyncMock,
    fof_repo: AsyncMock,
    mock_session_factory: MagicMock,
) -> FundStructuresService:
    """Service without an event bus — verifies no publish errors."""
    return FundStructuresService(
        master_feeder_repo=mf_repo,
        strategy_book_repo=sb_repo,
        fof_repo=fof_repo,
        session_factory=mock_session_factory,
        event_bus=None,
    )


# ---------------------------------------------------------------------------
# TestCreateMasterFeeder
# ---------------------------------------------------------------------------


class TestCreateMasterFeeder:
    async def test_returns_master_feeder_link(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        mf_repo.create_link.side_effect = lambda r, **kw: _stamp_mf_link(r)

        result = await service.create_master_feeder_link("master-alpha", "feeder-a", Decimal("0.4"))

        assert result.master_fund_slug == "master-alpha"
        assert result.feeder_fund_slug == "feeder-a"
        assert result.allocation_pct == Decimal("0.4")
        assert isinstance(result.id, UUID)

    async def test_calls_repo_create_link(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        mf_repo.create_link.side_effect = lambda r, **kw: _stamp_mf_link(r)

        await service.create_master_feeder_link("master-alpha", "feeder-a", Decimal("0.5"))

        mf_repo.create_link.assert_called_once()

    async def test_publishes_audit_event(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
        capture: EventCapture,
    ):
        mf_repo.create_link.side_effect = lambda r, **kw: _stamp_mf_link(r)

        await service.create_master_feeder_link("master-alpha", "feeder-a", Decimal("0.4"))

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].event_type == "fund_structures.link.created"
        assert audit_events[0].data["master_fund_slug"] == "master-alpha"
        assert audit_events[0].data["feeder_fund_slug"] == "feeder-a"
        assert audit_events[0].data["allocation_pct"] == "0.4"

    async def test_no_event_bus_does_not_raise(
        self,
        service_no_bus: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        mf_repo.create_link.side_effect = lambda r, **kw: _stamp_mf_link(r)

        result = await service_no_bus.create_master_feeder_link(
            "master-alpha", "feeder-a", Decimal("0.4")
        )
        assert result.master_fund_slug == "master-alpha"

    async def test_get_feeder_structure_returns_list(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        mf_repo.get_feeders_for_master.return_value = [
            _make_mf_link_record(feeder_fund_slug="feeder-a"),
            _make_mf_link_record(feeder_fund_slug="feeder-b"),
        ]

        results = await service.get_feeder_structure("master-alpha")

        assert len(results) == 2
        slugs = {r.feeder_fund_slug for r in results}
        assert slugs == {"feeder-a", "feeder-b"}

    async def test_allocate_feeder_subscription_with_link(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        link = _make_mf_link_record(allocation_pct=Decimal("0.5"))
        mf_repo.get_master_for_feeder.return_value = link

        result = await service.allocate_feeder_subscription("feeder-a", Decimal("1000000"))

        assert result.amount == Decimal("1000000")
        assert result.allocated_to_master == Decimal("500000.0")

    async def test_allocate_feeder_subscription_no_link(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        mf_repo.get_master_for_feeder.return_value = None

        result = await service.allocate_feeder_subscription("standalone", Decimal("250000"))

        assert result.allocated_to_master == Decimal(0)
        assert result.amount == Decimal("250000")

    async def test_compute_feeder_nav_with_link(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        link = _make_mf_link_record(allocation_pct=Decimal("0.4"))
        mf_repo.get_master_for_feeder.return_value = link

        nav = await service.compute_feeder_nav("feeder-a", Decimal("10000000"))

        assert nav == Decimal("4000000.0")

    async def test_compute_feeder_nav_no_link_returns_zero(
        self,
        service: FundStructuresService,
        mf_repo: AsyncMock,
    ):
        mf_repo.get_master_for_feeder.return_value = None

        nav = await service.compute_feeder_nav("standalone", Decimal("10000000"))

        assert nav == Decimal(0)


# ---------------------------------------------------------------------------
# TestCreateStrategyBook
# ---------------------------------------------------------------------------


class TestCreateStrategyBook:
    async def test_returns_strategy_book(
        self,
        service: FundStructuresService,
        sb_repo: AsyncMock,
    ):
        sb_repo.create.side_effect = lambda r, **kw: _stamp_strategy_book(r)

        result = await service.create_book(
            "alpha", "Equity Book", "strategy", target_pct=Decimal("0.6")
        )

        assert result.fund_slug == "alpha"
        assert result.name == "Equity Book"
        assert result.level == "strategy"
        assert result.target_allocation_pct == Decimal("0.6")
        assert result.parent_id is None

    async def test_create_child_book_with_parent(
        self,
        service: FundStructuresService,
        sb_repo: AsyncMock,
    ):
        parent_id = str(uuid4())
        sb_repo.create.side_effect = lambda r, **kw: _stamp_strategy_book(r)

        result = await service.create_book(
            "alpha",
            "US Large Cap",
            "sub_strategy",
            parent_id=parent_id,
            target_pct=Decimal("0.3"),
        )

        assert result.parent_id == UUID(parent_id)
        assert result.level == "sub_strategy"

    async def test_publishes_audit_event(
        self,
        service: FundStructuresService,
        sb_repo: AsyncMock,
        capture: EventCapture,
    ):
        sb_repo.create.side_effect = lambda r, **kw: _stamp_strategy_book(r)

        await service.create_book("alpha", "Equity Book", "strategy")

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].event_type == "fund_structures.book.created"
        assert audit_events[0].data["fund_slug"] == "alpha"
        assert audit_events[0].data["name"] == "Equity Book"
        assert audit_events[0].data["level"] == "strategy"

    async def test_get_book_tree_returns_all_books(
        self,
        service: FundStructuresService,
        sb_repo: AsyncMock,
    ):
        parent_id = str(uuid4())
        sb_repo.get_tree.return_value = [
            _make_strategy_book_record(name="Top Book", level="fund", parent_id=None),
            _make_strategy_book_record(name="Equity", level="strategy", parent_id=parent_id),
            _make_strategy_book_record(name="US LC", level="sub_strategy", parent_id=parent_id),
        ]

        results = await service.get_book_tree("alpha")

        assert len(results) == 3
        names = [r.name for r in results]
        assert "Top Book" in names
        assert "Equity" in names

    async def test_check_rebalance_computes_drift(
        self,
        service: FundStructuresService,
        sb_repo: AsyncMock,
    ):
        book_id = uuid4()
        record = _make_strategy_book_record(
            id=str(book_id),
            name="Equity",
            target_allocation_pct=Decimal("0.6"),
        )
        sb_repo.get_tree.return_value = [record]

        # Book is the only one, so it has 100% of NAV but target is 60% → drift = +0.4
        book_navs = {book_id: Decimal("1000000")}
        results = await service.check_rebalance("alpha", book_navs)

        assert len(results) == 1
        r = results[0]
        assert r.book_id == book_id
        assert r.target_pct == Decimal("0.6")
        assert r.drift_pct == pytest.approx(Decimal("0.4"), abs=Decimal("0.001"))
        # Positive drift → should sell (suggested amount > 0)
        assert r.suggested_trade_amount > 0

    async def test_check_rebalance_empty_navs_returns_empty(
        self,
        service: FundStructuresService,
        sb_repo: AsyncMock,
    ):
        sb_repo.get_tree.return_value = [_make_strategy_book_record()]

        results = await service.check_rebalance("alpha", {})

        assert results == []


# ---------------------------------------------------------------------------
# TestFundOfFundsHoldings
# ---------------------------------------------------------------------------


class TestFundOfFundsHoldings:
    async def test_add_holding_returns_fof_holding(
        self,
        service: FundStructuresService,
        fof_repo: AsyncMock,
    ):
        fof_repo.add_holding.side_effect = lambda r, **kw: _stamp_fof_holding(r)

        result = await service.add_fof_holding(
            "fof-alpha",
            "Fund B",
            Decimal("0.3"),
            underlying_slug="fund-b",
            is_internal=True,
        )

        assert result.fof_fund_slug == "fof-alpha"
        assert result.underlying_fund_name == "Fund B"
        assert result.allocation_pct == Decimal("0.3")
        assert result.is_internal is True

    async def test_add_external_holding(
        self,
        service: FundStructuresService,
        fof_repo: AsyncMock,
    ):
        fof_repo.add_holding.side_effect = lambda r, **kw: _stamp_fof_holding(r)

        result = await service.add_fof_holding(
            "fof-alpha",
            "Bridgewater All Weather",
            Decimal("0.25"),
            underlying_slug=None,
            is_internal=False,
        )

        assert result.underlying_fund_slug is None
        assert result.is_internal is False

    async def test_publishes_audit_event(
        self,
        service: FundStructuresService,
        fof_repo: AsyncMock,
        capture: EventCapture,
    ):
        fof_repo.add_holding.side_effect = lambda r, **kw: _stamp_fof_holding(r)

        await service.add_fof_holding(
            "fof-alpha", "Fund B", Decimal("0.3"), underlying_slug="fund-b", is_internal=True
        )

        audit_events = capture.get_by_topic("audit")
        assert len(audit_events) == 1
        assert audit_events[0].event_type == "fund_structures.fof.holding_added"
        assert audit_events[0].data["fof_fund_slug"] == "fof-alpha"
        assert audit_events[0].data["underlying_fund_name"] == "Fund B"
        assert audit_events[0].data["allocation_pct"] == "0.3"
        assert audit_events[0].data["is_internal"] is True

    async def test_get_fof_holdings_returns_list(
        self,
        service: FundStructuresService,
        fof_repo: AsyncMock,
    ):
        fof_repo.list_holdings.return_value = [
            _make_fof_holding_record(underlying_fund_name="Fund B", allocation_pct=Decimal("0.3")),
            _make_fof_holding_record(
                underlying_fund_name="Bridgewater", allocation_pct=Decimal("0.5")
            ),
        ]

        results = await service.get_fof_holdings("fof-alpha")

        assert len(results) == 2
        names = {r.underlying_fund_name for r in results}
        assert "Fund B" in names
        assert "Bridgewater" in names

    async def test_compute_fof_nav_sums_holdings(
        self,
        service: FundStructuresService,
        fof_repo: AsyncMock,
    ):
        fof_repo.list_holdings.return_value = [
            _make_fof_holding_record(current_nav=Decimal("500000")),
            _make_fof_holding_record(current_nav=Decimal("750000")),
            _make_fof_holding_record(current_nav=Decimal("250000")),
        ]

        result = await service.compute_fof_nav("fof-alpha")

        assert result.fof_fund_slug == "fof-alpha"
        assert result.total_nav == Decimal("1500000")
        assert len(result.holdings) == 3

    async def test_compute_fof_nav_empty_holdings(
        self,
        service: FundStructuresService,
        fof_repo: AsyncMock,
    ):
        fof_repo.list_holdings.return_value = []

        result = await service.compute_fof_nav("fof-empty")

        assert result.total_nav == Decimal(0)
        assert result.holdings == []

    async def test_update_holding_nav_delegates_to_repo(
        self,
        service: FundStructuresService,
        fof_repo: AsyncMock,
    ):
        holding_id = str(uuid4())

        await service.update_holding_nav(holding_id, Decimal("999999"))

        fof_repo.update_nav.assert_called_once_with(holding_id, Decimal("999999"), session=None)
