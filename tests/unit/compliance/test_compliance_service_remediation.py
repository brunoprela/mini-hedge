"""Additional unit tests for ComplianceService.suggest_remediation edge cases.

Covers lines 279-305 in services/compliance.py — instrument parsing from
violation message, zero-price handling, and excess_mv <= 0 path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.compliance.interfaces import ComplianceDecision
from app.modules.compliance.services.compliance import ComplianceService

_PID = uuid4()


def _make_violation_record(
    *,
    message: str = "AAPL is 15.00% of NAV (limit 10%)",
    current_value: Decimal = Decimal("15.0"),
    limit_value: Decimal = Decimal("10.0"),
) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.portfolio_id = str(_PID)
    r.rule_id = str(uuid4())
    r.rule_name = "conc_limit"
    r.severity = "block"
    r.breach_type = "active"
    r.message = message
    r.current_value = current_value
    r.limit_value = limit_value
    r.detected_at = datetime.now(timezone.utc)
    r.deadline_at = None
    r.resolved_at = None
    r.resolved_by = None
    r.resolution_type = None
    return r


def _make_position(
    instrument_id: str = "AAPL",
    quantity: Decimal = Decimal("100"),
    market_value: Decimal = Decimal("15000"),
    market_price: Decimal = Decimal("150"),
) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.quantity = quantity
    p.market_value = market_value
    p.market_price = market_price
    return p


def _make_service(
    *,
    violations: list | None = None,
    positions: list | None = None,
) -> ComplianceService:
    rule_repo = AsyncMock()
    violation_repo = AsyncMock()
    violation_repo.list_active_by_portfolio = AsyncMock(return_value=violations or [])

    pre_trade_gate = AsyncMock()
    pre_trade_gate.check_trade = AsyncMock(
        return_value=ComplianceDecision(approved=True, results=[], blocked_by=[])
    )

    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    return ComplianceService(
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        pre_trade_gate=pre_trade_gate,
        position_service=position_service,
    )


class TestPreTradeGateAccessor:
    def test_pre_trade_gate_property(self) -> None:
        """The pre_trade_gate property returns the injected gate."""
        svc = _make_service()
        assert svc.pre_trade_gate is svc._pre_trade_gate


class TestRemediationEdgeCases:
    @pytest.mark.asyncio
    async def test_instrument_not_in_positions_skipped(self) -> None:
        """Violation referencing an instrument not held is skipped."""
        violation = _make_violation_record(message="TSLA is 15.00% of NAV (limit 10%)")
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_message_without_is_keyword_skipped(self) -> None:
        """Violation with no ' is ' in message cannot parse instrument_id."""
        violation = _make_violation_record(message="No restricted instruments held.")
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_current_value_none_skipped(self) -> None:
        """Violation with current_value=None is skipped."""
        violation = _make_violation_record()
        violation.current_value = None
        positions = [_make_position("AAPL", Decimal("100"), Decimal("15000"))]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_zero_market_price_uses_implied_price(self) -> None:
        """When market_price is 0, the implied price from mv/qty is used."""
        violation = _make_violation_record(
            message="AAPL is 90.00% of NAV (limit 10%)",
            current_value=Decimal("90.0"),
            limit_value=Decimal("10.0"),
        )
        # market_price=0 but position has market_value / quantity ratio
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("90000"), Decimal("0")),
            _make_position("MSFT", Decimal("50"), Decimal("10000"), Decimal("200")),
        ]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        # Should still produce a suggestion using implied price
        assert len(suggestions) == 1
        assert suggestions[0].instrument_id == "AAPL"
        assert suggestions[0].quantity > 0

    @pytest.mark.asyncio
    async def test_none_market_price_with_quantity_uses_implied(self) -> None:
        """When market_price is None, implied price mv/qty is used."""
        violation = _make_violation_record(
            message="AAPL is 80.00% of NAV (limit 10%)",
            current_value=Decimal("80.0"),
            limit_value=Decimal("10.0"),
        )
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("80000"), None),
            _make_position("MSFT", Decimal("50"), Decimal("20000"), Decimal("400")),
        ]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        assert len(suggestions) == 1
        assert suggestions[0].quantity > 0

    @pytest.mark.asyncio
    async def test_excess_mv_zero_or_negative_skipped(self) -> None:
        """When the position is already below target, no suggestion generated."""
        violation = _make_violation_record(
            message="AAPL is 5.00% of NAV (limit 10%)",
            current_value=Decimal("5.0"),
            limit_value=Decimal("10.0"),
        )
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("5000"), Decimal("50")),
            _make_position("MSFT", Decimal("200"), Decimal("95000"), Decimal("475")),
        ]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_multiple_violations_produce_multiple_suggestions(self) -> None:
        """Each concentration violation can produce its own suggestion."""
        v1 = _make_violation_record(
            message="AAPL is 60.00% of NAV (limit 10%)",
            current_value=Decimal("60.0"),
            limit_value=Decimal("10.0"),
        )
        v2 = _make_violation_record(
            message="MSFT is 30.00% of NAV (limit 10%)",
            current_value=Decimal("30.0"),
            limit_value=Decimal("10.0"),
        )
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("60000"), Decimal("600")),
            _make_position("MSFT", Decimal("100"), Decimal("30000"), Decimal("300")),
            _make_position("JNJ", Decimal("100"), Decimal("10000"), Decimal("100")),
        ]
        svc = _make_service(violations=[v1, v2], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        assert len(suggestions) == 2
        ids = {s.instrument_id for s in suggestions}
        assert ids == {"AAPL", "MSFT"}

    @pytest.mark.asyncio
    async def test_limit_below_buffer_clamps_target_to_zero(self) -> None:
        """When limit_pct < 0.5, target_pct is clamped to 0 (line 289)."""
        violation = _make_violation_record(
            message="AAPL is 50.00% of NAV (limit 0.1%)",
            current_value=Decimal("50.0"),
            limit_value=Decimal("0.1"),  # < 0.5 buffer
        )
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("50000"), Decimal("500")),
            _make_position("MSFT", Decimal("200"), Decimal("50000"), Decimal("250")),
        ]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        # target_pct is clamped to 0, so sell the entire position value
        assert len(suggestions) == 1
        assert suggestions[0].instrument_id == "AAPL"

    @pytest.mark.asyncio
    async def test_tiny_excess_rounds_qty_to_zero_skipped(self) -> None:
        """When excess_mv / price rounds to 0, the suggestion is skipped (line 305)."""
        violation = _make_violation_record(
            message="AAPL is 10.01% of NAV (limit 10%)",
            current_value=Decimal("10.01"),
            limit_value=Decimal("10.0"),
        )
        # Very high price, very small excess => qty rounds to 0
        positions = [
            _make_position("AAPL", Decimal("1"), Decimal("100100"), Decimal("100100")),
            _make_position("MSFT", Decimal("1"), Decimal("899900"), Decimal("899900")),
        ]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_zero_quantity_zero_price_skipped(self) -> None:
        """When quantity is 0 and market_price is None, price calc fails gracefully."""
        violation = _make_violation_record(
            message="AAPL is 50.00% of NAV (limit 10%)",
            current_value=Decimal("50.0"),
            limit_value=Decimal("10.0"),
        )
        positions = [
            _make_position("AAPL", Decimal("0"), Decimal("50000"), None),
            _make_position("MSFT", Decimal("200"), Decimal("50000"), Decimal("250")),
        ]
        svc = _make_service(violations=[violation], positions=positions)

        suggestions = await svc.suggest_remediation(_PID)

        # quantity=0, market_price=None → tries mv/qty which divides by zero
        # Falls to price=None → skipped
        assert suggestions == []
