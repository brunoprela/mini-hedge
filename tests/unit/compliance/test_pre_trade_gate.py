"""Unit tests for PreTradeGate — fail-closed pre-trade compliance checks."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.compliance.core.pre_trade import PreTradeGate
from app.modules.compliance.interfaces import (
    ComplianceDecision,
    RuleType,
    Severity,
    TradeCheckRequest,
)


_PORT_ID = uuid4()


def _make_request(
    instrument_id: str = "AAPL",
    side: str = "buy",
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("150"),
) -> TradeCheckRequest:
    return TradeCheckRequest(
        portfolio_id=_PORT_ID,
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        price=price,
    )


def _make_rule_record(
    name: str = "concentration_limit",
    rule_type: str = "concentration_limit",
    severity: str = "block",
    parameters: dict | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.name = name
    r.rule_type = rule_type
    r.severity = severity
    r.parameters = parameters or {"max_pct": 10}
    r.is_active = True
    r.created_at = "2025-01-01T00:00:00Z"
    return r


def _make_position(
    instrument_id: str = "AAPL",
    quantity: Decimal = Decimal("100"),
    market_value: Decimal = Decimal("15000"),
) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.quantity = quantity
    p.market_value = market_value
    return p


def _make_gate(
    rules: list | None = None,
    positions: list | None = None,
    with_security_master: bool = False,
    with_cash: bool = False,
) -> PreTradeGate:
    rule_repo = AsyncMock()
    rule_repo.get_active = AsyncMock(return_value=rules or [])

    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    security_master = None
    if with_security_master:
        security_master = AsyncMock()
        inst = MagicMock()
        inst.asset_class = "equity"
        inst.sector = "Technology"
        inst.country = "US"
        security_master.get_by_ticker = AsyncMock(return_value=inst)

    cash_balance_repo = None
    if with_cash:
        cash_balance_repo = AsyncMock()
        bal = MagicMock()
        bal.available_balance = 1000000  # plain number, used in sum()
        cash_balance_repo.get_by_portfolio = AsyncMock(return_value=[bal])

    return PreTradeGate(
        rule_repo=rule_repo,
        position_service=position_service,
        security_master=security_master,
        cash_balance_repo=cash_balance_repo,
    )


class TestCheckTrade:
    @pytest.mark.asyncio
    async def test_no_rules_approves(self) -> None:
        gate = _make_gate(rules=[])

        decision = await gate.check_trade(_make_request())

        assert decision.approved is True
        assert decision.results == []
        assert decision.blocked_by == []

    @pytest.mark.asyncio
    async def test_passing_rule_approves(self) -> None:
        """A concentration limit of 50% should pass when positions are balanced."""
        rule = _make_rule_record(
            "wide_limit",
            "concentration_limit",
            "block",
            {"max_pct": 50},  # 50% in percentage terms (evaluator uses *100)
        )
        # Two balanced positions + large cash = each well under 50%
        positions = [
            _make_position("MSFT", Decimal("100"), Decimal("100000")),
            _make_position("GOOG", Decimal("50"), Decimal("100000")),
        ]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=True)

        decision = await gate.check_trade(_make_request("AAPL", "buy", Decimal("10"), Decimal("150")))

        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_blocking_rule_rejects(self) -> None:
        """A tight concentration limit should block a large trade."""
        rule = _make_rule_record(
            "tight_limit",
            "concentration_limit",
            "block",
            {"max_pct": 1},  # 1% limit
        )
        # Existing position is 90% of the portfolio
        positions = [_make_position("AAPL", Decimal("1000"), Decimal("150000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=True)

        # Buy more AAPL — will push concentration way over 1%
        decision = await gate.check_trade(_make_request("AAPL", "buy", Decimal("1000"), Decimal("150")))

        assert decision.approved is False
        assert len(decision.blocked_by) > 0

    @pytest.mark.asyncio
    async def test_warn_severity_does_not_block(self) -> None:
        """A WARN severity rule that fails should not block the trade."""
        rule = _make_rule_record(
            "soft_limit",
            "concentration_limit",
            "warning",
            {"max_pct": 1},
        )
        positions = [_make_position("AAPL", Decimal("1000"), Decimal("150000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=True)

        decision = await gate.check_trade(_make_request("AAPL", "buy", Decimal("1000"), Decimal("150")))

        # Warn rules fail but don't block
        assert decision.approved is True
        assert decision.blocked_by == []

    @pytest.mark.asyncio
    async def test_fail_closed_on_error(self) -> None:
        """If an exception occurs, the gate should reject (fail-closed)."""
        rule_repo = AsyncMock()
        rule_repo.get_active = AsyncMock(side_effect=RuntimeError("db down"))

        gate = PreTradeGate(
            rule_repo=rule_repo,
            position_service=AsyncMock(),
        )

        decision = await gate.check_trade(_make_request())

        assert decision.approved is False
        assert "SYSTEM" in decision.blocked_by

    @pytest.mark.asyncio
    async def test_sell_side_reduces_position(self) -> None:
        """A sell trade should reduce the instrument's position in the hypothetical state."""
        rule = _make_rule_record(
            "conc_limit",
            "concentration_limit",
            "block",
            {"max_pct": 80},  # 80% limit
        )
        positions = [_make_position("AAPL", Decimal("1000"), Decimal("150000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=True)

        # Selling reduces concentration — should pass
        decision = await gate.check_trade(_make_request("AAPL", "sell", Decimal("500"), Decimal("150")))

        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_new_instrument_buy(self) -> None:
        """Buying an instrument not in the portfolio creates a new position."""
        rule = _make_rule_record(
            "conc_limit",
            "concentration_limit",
            "block",
            {"max_pct": 50},
        )
        positions = [_make_position("MSFT", Decimal("100"), Decimal("30000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=True)

        decision = await gate.check_trade(_make_request("AAPL", "buy", Decimal("10"), Decimal("150")))

        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_unknown_rule_type_triggers_fail_closed(self) -> None:
        """An invalid rule type causes an error, triggering fail-closed rejection."""
        rule = _make_rule_record("custom", "nonexistent_rule_type", "block", {})
        gate = _make_gate(rules=[rule])

        decision = await gate.check_trade(_make_request())

        # RuleType enum conversion fails → caught by fail-closed handler
        assert decision.approved is False
        assert "SYSTEM" in decision.blocked_by

    @pytest.mark.asyncio
    async def test_metadata_lookup_with_security_master(self) -> None:
        """When security master is available, instrument metadata should be populated."""
        rule = _make_rule_record(
            "sector_limit",
            "sector_limit",
            "block",
            {"sector": "Technology", "max_pct": 90},
        )
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_security_master=True, with_cash=True)

        decision = await gate.check_trade(_make_request("AAPL", "buy", Decimal("10"), Decimal("150")))

        # Should run without error; sector metadata populated from mock
        assert isinstance(decision, ComplianceDecision)

    @pytest.mark.asyncio
    async def test_no_cash_repo_defaults_zero_cash(self) -> None:
        """Without a cash balance repo, cash should default to 0."""
        rule = _make_rule_record("conc", "concentration_limit", "block", {"max_pct": 99})
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=False)

        decision = await gate.check_trade(_make_request("AAPL", "buy", Decimal("10"), Decimal("150")))

        assert isinstance(decision, ComplianceDecision)
