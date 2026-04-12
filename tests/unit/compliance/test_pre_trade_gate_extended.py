"""Extended tests for PreTradeGate — covering edge cases in _evaluate and _lookup."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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
    name: str = "test_rule",
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
    security_master: AsyncMock | None = None,
    with_cash: bool = False,
) -> PreTradeGate:
    rule_repo = AsyncMock()
    rule_repo.get_active = AsyncMock(return_value=rules or [])

    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    cash_balance_repo = None
    if with_cash:
        cash_balance_repo = AsyncMock()
        bal = MagicMock()
        bal.available_balance = 1000000
        cash_balance_repo.get_by_portfolio = AsyncMock(return_value=[bal])

    return PreTradeGate(
        rule_repo=rule_repo,
        position_service=position_service,
        security_master=security_master,
        cash_balance_repo=cash_balance_repo,
    )


class TestEvaluatorNotFound:
    """Lines 111-115: evaluator is None for a valid rule type."""

    @pytest.mark.asyncio
    async def test_missing_evaluator_skipped_gracefully(self) -> None:
        """When EVALUATOR_REGISTRY has no evaluator for a rule type, the rule is skipped."""
        rule = _make_rule_record("conc", "concentration_limit", "block", {"max_pct": 10})
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=True)

        # Patch registry to be empty so evaluator lookup returns None
        with patch("app.modules.compliance.core.pre_trade.EVALUATOR_REGISTRY", {}):
            decision = await gate.check_trade(_make_request())

        # No evaluators found → no blocking, approved
        assert decision.approved is True
        assert decision.blocked_by == []


class TestLookupMetadataException:
    """Lines 145-146: exception in security master lookup returns defaults."""

    @pytest.mark.asyncio
    async def test_security_master_exception_returns_defaults(self) -> None:
        """When security master raises, metadata defaults to empty strings."""
        failing_sm = AsyncMock()
        failing_sm.get_by_ticker = AsyncMock(side_effect=RuntimeError("service down"))

        rule = _make_rule_record("sector_limit", "sector_limit", "block", {"max_pct": 90})
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        gate = _make_gate(
            rules=[rule],
            positions=positions,
            security_master=failing_sm,
            with_cash=True,
        )

        decision = await gate.check_trade(_make_request())

        # Should not fail — metadata defaults gracefully
        assert isinstance(decision, ComplianceDecision)

    @pytest.mark.asyncio
    async def test_security_master_none_asset_class(self) -> None:
        """When inst.asset_class is None, it should default to empty string."""
        sm = AsyncMock()
        inst = MagicMock()
        inst.asset_class = None
        inst.sector = None
        inst.country = None
        sm.get_by_ticker = AsyncMock(return_value=inst)

        rule = _make_rule_record("conc", "concentration_limit", "block", {"max_pct": 99})
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        gate = _make_gate(
            rules=[rule],
            positions=positions,
            security_master=sm,
            with_cash=True,
        )

        decision = await gate.check_trade(_make_request())
        assert isinstance(decision, ComplianceDecision)


class TestNewInstrumentSell:
    """Selling an instrument not in portfolio creates a negative position."""

    @pytest.mark.asyncio
    async def test_sell_new_instrument_creates_short(self) -> None:
        rule = _make_rule_record("short_selling", "short_selling", "block", {"allow_short": False})
        positions = [_make_position("MSFT", Decimal("100"), Decimal("30000"))]
        gate = _make_gate(rules=[rule], positions=positions, with_cash=True)

        decision = await gate.check_trade(_make_request("AAPL", "sell", Decimal("10"), Decimal("150")))

        # Short selling is not allowed, selling creates a short → should block
        assert decision.approved is False
