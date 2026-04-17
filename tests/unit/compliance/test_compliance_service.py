"""Unit tests for ComplianceService — rules, trade checks, violations, remediation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.compliance.interfaces import (
    ComplianceDecision,
    RuleType,
    Severity,
    TradeCheckRequest,
    UpdateRuleRequest,
)
from app.modules.compliance.services.compliance import ComplianceService

ZERO = Decimal(0)
_PID = uuid4()


def _make_rule_record(
    name: str = "conc_limit",
    rule_type: str = "concentration_limit",
    severity: str = "block",
    parameters: dict | None = None,
    is_active: bool = True,
) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.name = name
    r.rule_type = rule_type
    r.severity = severity
    r.parameters = parameters or {"max_pct": 10}
    r.is_active = is_active
    r.grace_period_hours = None
    r.created_at = datetime.now(timezone.utc)
    r.fund_slug = "test-fund"
    return r


def _make_violation_record(
    rule_name: str = "conc_limit",
    severity: str = "block",
    message: str = "AAPL is 15.00% of NAV (limit 10%)",
    current_value: Decimal = Decimal("15.0"),
    limit_value: Decimal = Decimal("10.0"),
    resolved: bool = False,
) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.portfolio_id = str(_PID)
    r.rule_id = str(uuid4())
    r.rule_name = rule_name
    r.severity = severity
    r.breach_type = "active"
    r.message = message
    r.current_value = current_value
    r.limit_value = limit_value
    r.detected_at = datetime.now(timezone.utc)
    r.deadline_at = None
    r.resolved_at = datetime.now(timezone.utc) if resolved else None
    r.resolved_by = "user-1" if resolved else None
    r.resolution_type = "manual" if resolved else None
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


async def _insert_with_id(record: object, **kw: object) -> object:
    if getattr(record, "id", None) is None:
        record.id = str(uuid4())
    if getattr(record, "created_at", None) is None:
        record.created_at = datetime.now(timezone.utc)
    return record


def _make_service(
    rules: list | None = None,
    violations: list | None = None,
    positions: list | None = None,
    with_audit: bool = False,
    with_event_bus: bool = False,
    with_positions: bool = False,
) -> ComplianceService:
    rule_repo = AsyncMock()
    rule_repo.list_all = AsyncMock(return_value=rules or [])
    rule_repo.insert = AsyncMock(side_effect=_insert_with_id)
    rule_repo.update = AsyncMock(return_value=None)

    violation_repo = AsyncMock()
    violation_repo.list_active_by_portfolio = AsyncMock(return_value=violations or [])
    violation_repo.resolve = AsyncMock(return_value=None)

    pre_trade_gate = AsyncMock()
    pre_trade_gate.check_trade = AsyncMock(
        return_value=ComplianceDecision(approved=True, results=[], blocked_by=[])
    )

    audit_repo = AsyncMock() if with_audit else None
    event_bus = AsyncMock() if with_event_bus else None
    position_service = AsyncMock() if with_positions else None
    if position_service:
        position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    return ComplianceService(
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        pre_trade_gate=pre_trade_gate,
        audit_repo=audit_repo,
        event_bus=event_bus,
        position_service=position_service,
    )


class TestRules:
    @pytest.mark.asyncio
    async def test_get_rules(self) -> None:
        rules = [_make_rule_record("rule_a"), _make_rule_record("rule_b")]
        svc = _make_service(rules=rules)

        result = await svc.get_rules()

        assert len(result) == 2
        assert result[0].name == "rule_a"

    @pytest.mark.asyncio
    async def test_create_rule(self) -> None:
        svc = _make_service(with_audit=True)

        with patch("app.modules.compliance.services.compliance.TenantSessionFactory") as mock_tsf:
            mock_tsf.current_fund_slug.return_value = "test-fund"
            rule = await svc.create_rule(
                "new_rule", RuleType.CONCENTRATION_LIMIT, Severity.BLOCK,
                {"max_pct": 20}, actor_id="user-1",
            )

        svc._rule_repo.insert.assert_called_once()
        svc._audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rule_no_audit(self) -> None:
        svc = _make_service(with_audit=False)

        with patch("app.modules.compliance.services.compliance.TenantSessionFactory") as mock_tsf:
            mock_tsf.current_fund_slug.return_value = "test-fund"
            await svc.create_rule(
                "rule", RuleType.CONCENTRATION_LIMIT, Severity.WARNING,
                {"max_pct": 50},
            )

        svc._rule_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_rule_success(self) -> None:
        record = _make_rule_record()
        svc = _make_service(with_audit=True)
        svc._rule_repo.update = AsyncMock(return_value=record)

        updates = UpdateRuleRequest(name="updated_name")
        result = await svc.update_rule(UUID(record.id), updates, actor_id="user-1")

        assert result.name == record.name
        svc._audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_rule_not_found(self) -> None:
        svc = _make_service()

        with pytest.raises(LookupError, match="not found"):
            await svc.update_rule(uuid4(), UpdateRuleRequest(name="x"))


class TestCheckTrade:
    @pytest.mark.asyncio
    async def test_delegates_to_gate(self) -> None:
        svc = _make_service()

        request = TradeCheckRequest(
            portfolio_id=_PID,
            instrument_id="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150"),
        )
        result = await svc.check_trade(request)

        assert result.approved is True
        svc._pre_trade_gate.check_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_event_on_approval(self) -> None:
        svc = _make_service(with_event_bus=True)

        request = TradeCheckRequest(
            portfolio_id=_PID,
            instrument_id="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150"),
        )

        with patch("app.modules.compliance.services.compliance.TenantSessionFactory") as mock_tsf:
            mock_tsf.current_fund_slug.return_value = "test-fund"
            await svc.check_trade(request)

        svc._event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_event_bus_skips_publish(self) -> None:
        svc = _make_service(with_event_bus=False)

        request = TradeCheckRequest(
            portfolio_id=_PID, instrument_id="AAPL", side="buy",
            quantity=Decimal("100"), price=Decimal("150"),
        )
        result = await svc.check_trade(request)

        assert result.approved is True


class TestViolations:
    @pytest.mark.asyncio
    async def test_get_violations(self) -> None:
        violations = [_make_violation_record()]
        svc = _make_service(violations=violations)

        result = await svc.get_violations(_PID)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_resolve_violation(self) -> None:
        record = _make_violation_record(resolved=True)
        svc = _make_service(with_audit=True)
        svc._violation_repo.resolve = AsyncMock(return_value=record)

        result = await svc.resolve_violation(UUID(record.id), "user-1")

        assert result.resolved_by == "user-1"
        svc._audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_violation_not_found(self) -> None:
        svc = _make_service()

        with pytest.raises(LookupError, match="not found"):
            await svc.resolve_violation(uuid4(), "user-1")

    @pytest.mark.asyncio
    async def test_waive_violation(self) -> None:
        record = _make_violation_record(resolved=True)
        record.resolution_type = "waived"
        svc = _make_service(with_audit=True)
        svc._violation_repo.resolve = AsyncMock(return_value=record)

        result = await svc.waive_violation(UUID(record.id), "compliance-officer", "accepted risk")

        svc._violation_repo.resolve.assert_called_once()
        svc._audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_waive_violation_not_found(self) -> None:
        svc = _make_service()

        with pytest.raises(LookupError, match="not found"):
            await svc.waive_violation(uuid4(), "user-1", "reason")


class TestRemediation:
    @pytest.mark.asyncio
    async def test_suggest_remediation_basic(self) -> None:
        violation = _make_violation_record(
            message="AAPL is 15.00% of NAV (limit 10%)",
            current_value=Decimal("15.0"),
            limit_value=Decimal("10.0"),
        )
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("15000"), Decimal("150")),
            _make_position("MSFT", Decimal("200"), Decimal("85000"), Decimal("425")),
        ]
        svc = _make_service(violations=[violation], positions=positions, with_positions=True)

        suggestions = await svc.suggest_remediation(_PID)

        assert len(suggestions) == 1
        assert suggestions[0].instrument_id == "AAPL"
        assert suggestions[0].side == "sell"
        assert suggestions[0].quantity > ZERO

    @pytest.mark.asyncio
    async def test_suggest_remediation_no_position_service(self) -> None:
        svc = _make_service(with_positions=False)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_suggest_remediation_no_violations(self) -> None:
        svc = _make_service(violations=[], positions=[], with_positions=True)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_suggest_remediation_no_limit_value(self) -> None:
        violation = _make_violation_record()
        violation.limit_value = None
        svc = _make_service(violations=[violation], positions=[_make_position()], with_positions=True)

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_suggest_remediation_zero_nav(self) -> None:
        violation = _make_violation_record()
        # All positions with zero market value → NAV = 0
        svc = _make_service(
            violations=[violation],
            positions=[_make_position("AAPL", Decimal("100"), ZERO)],
            with_positions=True,
        )

        suggestions = await svc.suggest_remediation(_PID)

        assert suggestions == []
