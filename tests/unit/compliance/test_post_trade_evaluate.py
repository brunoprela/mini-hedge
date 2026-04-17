"""Unit tests for PostTradeMonitor._evaluate_portfolio and helpers.

Covers the full evaluation flow: loading rules, building state,
detecting new violations, auto-resolving existing violations,
and publishing events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.compliance.core.post_trade import PostTradeMonitor
from app.shared.events import InProcessEventBus
from app.shared.schema_registry import fund_topic
from tests.factories import DEFAULT_PORTFOLIO_ID, make_base_event
from tests.helpers import EventCapture


FUND_SLUG = "alpha"
NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule_record(
    *,
    rule_type: str = "concentration_limit",
    name: str = "conc_limit",
    severity: str = "block",
    parameters: dict | None = None,
    grace_period_hours: int | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.name = name
    r.rule_type = rule_type
    r.severity = severity
    r.parameters = parameters or {"max_pct": 10}
    r.is_active = True
    r.grace_period_hours = grace_period_hours
    r.created_at = NOW
    return r


def _make_position_record(
    instrument_id: str = "AAPL",
    quantity: Decimal = Decimal("100"),
    market_value: Decimal = Decimal("150000"),
    market_price: Decimal = Decimal("150"),
) -> MagicMock:
    r = MagicMock()
    r.portfolio_id = str(DEFAULT_PORTFOLIO_ID)
    r.instrument_id = instrument_id
    r.quantity = quantity
    r.avg_cost = Decimal("140")
    r.cost_basis = Decimal("14000")
    r.market_price = market_price
    r.market_value = market_value
    r.unrealized_pnl = Decimal("1000")
    r.currency = "USD"
    r.last_updated = NOW
    return r


def _make_violation_record(
    rule_id: str | None = None,
    rule_name: str = "conc_limit",
) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.portfolio_id = str(DEFAULT_PORTFOLIO_ID)
    r.rule_id = rule_id or str(uuid4())
    r.rule_name = rule_name
    r.severity = "block"
    r.message = "AAPL is 90.00% of NAV (limit 10%)"
    r.current_value = Decimal("90.0")
    r.limit_value = Decimal("10.0")
    r.breach_type = "active"
    r.detected_at = NOW
    r.deadline_at = None
    r.resolved_at = None
    r.resolved_by = None
    r.resolution_type = None
    return r


def _make_monitor(
    *,
    rules: list | None = None,
    positions: list | None = None,
    violations: list | None = None,
    with_event_bus: bool = True,
    with_security_master: bool = False,
    with_cash_balance: bool = False,
) -> PostTradeMonitor:
    sf = MagicMock()
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm

    rule_repo = AsyncMock()
    rule_repo.list_active = AsyncMock(return_value=rules if rules is not None else [])

    violation_repo = AsyncMock()
    violation_repo.list_active_by_portfolio = AsyncMock(
        return_value=violations if violations is not None else []
    )
    violation_repo.insert = AsyncMock()
    violation_repo.resolve = AsyncMock()

    position_repo = AsyncMock()
    position_repo.get_by_portfolio = AsyncMock(
        return_value=positions if positions is not None else []
    )

    event_bus = AsyncMock() if with_event_bus else None

    security_master = None
    if with_security_master:
        security_master = AsyncMock()
        inst = MagicMock()
        inst.asset_class = "equity"
        inst.sector = "Technology"
        inst.country = "US"
        security_master.get_by_ticker = AsyncMock(return_value=inst)

    cash_balance_repo = None
    if with_cash_balance:
        cash_balance_repo = AsyncMock()
        bal = MagicMock()
        bal.available_balance = 0
        cash_balance_repo.get_by_portfolio = AsyncMock(return_value=[bal])

    monitor = PostTradeMonitor(
        session_factory=sf,
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        position_repo=position_repo,
        security_master=security_master,
        event_bus=event_bus,
        cash_balance_repo=cash_balance_repo,
    )
    return monitor


# ---------------------------------------------------------------------------
# Tests for _evaluate_portfolio full flow
# ---------------------------------------------------------------------------


class TestEvaluatePortfolioFlow:
    """Tests covering the full _evaluate_portfolio path (lines 131-218)."""

    @pytest.mark.asyncio
    async def test_new_violation_detected_and_persisted(self) -> None:
        """When a rule fails and no existing violation, a new one is created."""
        rule = _make_rule_record(
            rule_type="concentration_limit",
            parameters={"max_pct": 5},
        )
        pos = _make_position_record("AAPL", Decimal("100"), Decimal("900000"))
        monitor = _make_monitor(rules=[rule], positions=[pos])

        await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=False)

        monitor._violation_repo.insert.assert_called_once()
        inserted = monitor._violation_repo.insert.call_args[0][0]
        assert inserted.rule_id == rule.id
        assert inserted.breach_type == "active"

    @pytest.mark.asyncio
    async def test_passive_violation_gets_deadline(self) -> None:
        """A passive breach with grace_period_hours gets a deadline_at."""
        rule = _make_rule_record(
            rule_type="concentration_limit",
            parameters={"max_pct": 5},
            grace_period_hours=24,
        )
        pos = _make_position_record("AAPL", Decimal("100"), Decimal("900000"))
        monitor = _make_monitor(rules=[rule], positions=[pos])

        await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=True)

        inserted = monitor._violation_repo.insert.call_args[0][0]
        assert inserted.breach_type == "passive"
        assert inserted.deadline_at is not None

    @pytest.mark.asyncio
    async def test_existing_violation_auto_resolved_when_passes(self) -> None:
        """When a rule passes and there's an existing violation, auto-resolve it."""
        rule = _make_rule_record(
            rule_type="concentration_limit",
            parameters={"max_pct": 99},  # Very wide limit — will pass
        )
        # Two positions so no single name exceeds 99%
        pos_a = _make_position_record("AAPL", Decimal("100"), Decimal("50000"))
        pos_b = _make_position_record("MSFT", Decimal("100"), Decimal("50000"))
        existing_violation = _make_violation_record(rule_id=rule.id)
        monitor = _make_monitor(
            rules=[rule],
            positions=[pos_a, pos_b],
            violations=[existing_violation],
        )

        await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=False)

        monitor._violation_repo.resolve.assert_called_once()
        call_args = monitor._violation_repo.resolve.call_args
        assert call_args[0][0] == UUID(existing_violation.id)
        assert call_args[1]["resolution_type"] == "auto"

    @pytest.mark.asyncio
    async def test_no_positions_returns_early(self) -> None:
        """When there are no positions, evaluation returns early."""
        rule = _make_rule_record()
        monitor = _make_monitor(rules=[rule], positions=[])

        await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=False)

        monitor._violation_repo.insert.assert_not_called()
        monitor._violation_repo.resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_publishes_violation_event(self) -> None:
        """A new violation triggers an event publish."""
        rule = _make_rule_record(
            rule_type="concentration_limit",
            parameters={"max_pct": 5},
        )
        pos = _make_position_record("AAPL", Decimal("100"), Decimal("900000"))
        monitor = _make_monitor(rules=[rule], positions=[pos])

        await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=False)

        monitor._event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_publishes_resolved_event(self) -> None:
        """Auto-resolving a violation publishes a resolved event."""
        rule = _make_rule_record(
            rule_type="concentration_limit",
            parameters={"max_pct": 99},
        )
        # Two positions so each is 50% < 99% limit
        pos_a = _make_position_record("AAPL", Decimal("100"), Decimal("50000"))
        pos_b = _make_position_record("MSFT", Decimal("100"), Decimal("50000"))
        existing_violation = _make_violation_record(rule_id=rule.id)
        monitor = _make_monitor(
            rules=[rule],
            positions=[pos_a, pos_b],
            violations=[existing_violation],
        )

        await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=False)

        # At least one publish call for the resolution
        monitor._event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_unknown_evaluator_skipped(self) -> None:
        """A rule with an unknown rule_type is silently skipped."""
        # We mock the RuleType to avoid ValueError — instead set a valid rule_type
        # that has no evaluator by using a patched EVALUATOR_REGISTRY
        rule = _make_rule_record(
            rule_type="concentration_limit",
            parameters={"max_pct": 10},
        )
        pos = _make_position_record("AAPL", Decimal("100"), Decimal("150000"))
        monitor = _make_monitor(rules=[rule], positions=[pos])

        with patch(
            "app.modules.compliance.core.post_trade.EVALUATOR_REGISTRY",
            {},
        ):
            await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=False)

        monitor._violation_repo.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_new_violation_when_already_exists(self) -> None:
        """When a rule fails but a violation already exists, do not create another."""
        rule = _make_rule_record(
            rule_type="concentration_limit",
            parameters={"max_pct": 5},
        )
        pos = _make_position_record("AAPL", Decimal("100"), Decimal("900000"))
        existing = _make_violation_record(rule_id=rule.id)
        monitor = _make_monitor(rules=[rule], positions=[pos], violations=[existing])

        await monitor._evaluate_portfolio(DEFAULT_PORTFOLIO_ID, FUND_SLUG, is_passive=False)

        # Should not insert a new violation
        monitor._violation_repo.insert.assert_not_called()
        # Should not resolve (still failing)
        monitor._violation_repo.resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for _publish_violation (lines 225-251)
# ---------------------------------------------------------------------------


class TestPublishViolation:
    @pytest.mark.asyncio
    async def test_publishes_to_compliance_topic(self) -> None:
        monitor = _make_monitor()
        record = _make_violation_record()

        await monitor._publish_violation(record, DEFAULT_PORTFOLIO_ID, FUND_SLUG)

        monitor._event_bus.publish.assert_called_once()
        topic = monitor._event_bus.publish.call_args[0][0]
        assert "compliance.violations" in topic

    @pytest.mark.asyncio
    async def test_skips_when_no_event_bus(self) -> None:
        monitor = _make_monitor(with_event_bus=False)
        record = _make_violation_record()

        # Should not raise
        await monitor._publish_violation(record, DEFAULT_PORTFOLIO_ID, FUND_SLUG)

    @pytest.mark.asyncio
    async def test_event_data_contains_violation_details(self) -> None:
        monitor = _make_monitor()
        record = _make_violation_record()

        await monitor._publish_violation(record, DEFAULT_PORTFOLIO_ID, FUND_SLUG)

        event = monitor._event_bus.publish.call_args[0][1]
        assert event.data["rule_name"] == record.rule_name
        assert event.data["severity"] == record.severity
        assert event.data["violation_id"] == record.id

    @pytest.mark.asyncio
    async def test_deadline_at_included_when_set(self) -> None:
        monitor = _make_monitor()
        record = _make_violation_record()
        record.deadline_at = NOW

        await monitor._publish_violation(record, DEFAULT_PORTFOLIO_ID, FUND_SLUG)

        event = monitor._event_bus.publish.call_args[0][1]
        assert event.data["deadline_at"] is not None

    @pytest.mark.asyncio
    async def test_deadline_at_none_when_not_set(self) -> None:
        monitor = _make_monitor()
        record = _make_violation_record()
        record.deadline_at = None

        await monitor._publish_violation(record, DEFAULT_PORTFOLIO_ID, FUND_SLUG)

        event = monitor._event_bus.publish.call_args[0][1]
        assert event.data["deadline_at"] is None


# ---------------------------------------------------------------------------
# Tests for _publish_violation_resolved (lines 256-280)
# ---------------------------------------------------------------------------


class TestPublishViolationResolved:
    @pytest.mark.asyncio
    async def test_publishes_resolved_event(self) -> None:
        monitor = _make_monitor()
        record = _make_violation_record()

        await monitor._publish_violation_resolved(record, DEFAULT_PORTFOLIO_ID, FUND_SLUG)

        monitor._event_bus.publish.assert_called_once()
        event = monitor._event_bus.publish.call_args[0][1]
        assert "Auto-resolved" in event.data["message"]

    @pytest.mark.asyncio
    async def test_skips_when_no_event_bus(self) -> None:
        monitor = _make_monitor(with_event_bus=False)
        record = _make_violation_record()

        # Should not raise
        await monitor._publish_violation_resolved(record, DEFAULT_PORTFOLIO_ID, FUND_SLUG)


# ---------------------------------------------------------------------------
# Tests for _lookup_instrument_metadata (lines 285-299)
# ---------------------------------------------------------------------------


class TestLookupInstrumentMetadata:
    @pytest.mark.asyncio
    async def test_returns_defaults_without_security_master(self) -> None:
        monitor = _make_monitor(with_security_master=False)
        result = await monitor._lookup_instrument_metadata("AAPL")
        assert result == ("", "", "")

    @pytest.mark.asyncio
    async def test_returns_metadata_from_security_master(self) -> None:
        monitor = _make_monitor(with_security_master=True)
        result = await monitor._lookup_instrument_metadata("AAPL")
        assert result == ("equity", "Technology", "US")

    @pytest.mark.asyncio
    async def test_returns_defaults_on_exception(self) -> None:
        monitor = _make_monitor(with_security_master=True)
        monitor._security_master_service.get_by_ticker = AsyncMock(
            side_effect=RuntimeError("not found")
        )
        result = await monitor._lookup_instrument_metadata("AAPL")
        assert result == ("", "", "")


# ---------------------------------------------------------------------------
# Tests for _build_actual_state (lines 301-327)
# ---------------------------------------------------------------------------


class TestBuildActualState:
    @pytest.mark.asyncio
    async def test_builds_state_from_positions(self) -> None:
        from app.modules.positions.interfaces import Position

        pos = Position(
            portfolio_id=DEFAULT_PORTFOLIO_ID,
            instrument_id="AAPL",
            quantity=Decimal("100"),
            avg_cost=Decimal("140"),
            cost_basis=Decimal("14000"),
            market_price=Decimal("150"),
            market_value=Decimal("15000"),
            unrealized_pnl=Decimal("1000"),
            currency="USD",
            last_updated=NOW,
        )
        monitor = _make_monitor(with_security_master=False)

        state = await monitor._build_actual_state(DEFAULT_PORTFOLIO_ID, [pos])

        assert "AAPL" in state.positions
        assert state.positions["AAPL"].market_value == Decimal("15000")
        assert state.nav > 0

    @pytest.mark.asyncio
    async def test_includes_cash_balance(self) -> None:
        from app.modules.positions.interfaces import Position

        pos = Position(
            portfolio_id=DEFAULT_PORTFOLIO_ID,
            instrument_id="AAPL",
            quantity=Decimal("100"),
            avg_cost=Decimal("140"),
            cost_basis=Decimal("14000"),
            market_price=Decimal("150"),
            market_value=Decimal("15000"),
            unrealized_pnl=Decimal("1000"),
            currency="USD",
            last_updated=NOW,
        )
        monitor = _make_monitor(with_cash_balance=True)

        state = await monitor._build_actual_state(DEFAULT_PORTFOLIO_ID, [pos])

        # NAV = positions (15000) + cash (0) = 15000
        assert state.nav == Decimal("15000")

    @pytest.mark.asyncio
    async def test_no_cash_repo_defaults_zero(self) -> None:
        from app.modules.positions.interfaces import Position

        pos = Position(
            portfolio_id=DEFAULT_PORTFOLIO_ID,
            instrument_id="AAPL",
            quantity=Decimal("100"),
            avg_cost=Decimal("140"),
            cost_basis=Decimal("14000"),
            market_price=Decimal("150"),
            market_value=Decimal("15000"),
            unrealized_pnl=Decimal("1000"),
            currency="USD",
            last_updated=NOW,
        )
        monitor = _make_monitor(with_cash_balance=False)

        state = await monitor._build_actual_state(DEFAULT_PORTFOLIO_ID, [pos])

        # NAV = positions only
        assert state.nav == Decimal("15000")

    @pytest.mark.asyncio
    async def test_metadata_populated_from_security_master(self) -> None:
        from app.modules.positions.interfaces import Position

        pos = Position(
            portfolio_id=DEFAULT_PORTFOLIO_ID,
            instrument_id="AAPL",
            quantity=Decimal("100"),
            avg_cost=Decimal("140"),
            cost_basis=Decimal("14000"),
            market_price=Decimal("150"),
            market_value=Decimal("15000"),
            unrealized_pnl=Decimal("1000"),
            currency="USD",
            last_updated=NOW,
        )
        monitor = _make_monitor(with_security_master=True)

        state = await monitor._build_actual_state(DEFAULT_PORTFOLIO_ID, [pos])

        info = state.positions["AAPL"]
        assert info.asset_class == "equity"
        assert info.sector == "Technology"
        assert info.country == "US"


# ---------------------------------------------------------------------------
# Tests for handle_mtm_update missing fund_slug
# ---------------------------------------------------------------------------


class TestHandleMtmUpdateMissingFundSlug:
    @pytest.mark.asyncio
    async def test_missing_fund_slug_returns_early(self) -> None:
        monitor = _make_monitor()
        event = make_base_event(
            event_type="pnl.mark_to_market",
            data={"portfolio_id": str(DEFAULT_PORTFOLIO_ID)},
            fund_slug="alpha",
        )
        event = event.model_copy(update={"fund_slug": None})

        await monitor.handle_mtm_update(event)

        monitor._rule_repo.list_active.assert_not_called()

    @pytest.mark.asyncio
    async def test_mtm_error_is_caught(self) -> None:
        monitor = _make_monitor()
        event = make_base_event(
            event_type="pnl.mark_to_market",
            data={"portfolio_id": str(DEFAULT_PORTFOLIO_ID)},
            fund_slug="alpha",
        )
        monitor._evaluate_portfolio = AsyncMock(side_effect=RuntimeError("boom"))

        # Should not propagate
        await monitor.handle_mtm_update(event)
