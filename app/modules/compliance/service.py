"""Compliance service — orchestrates rules, checks, and violations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.compliance.interface import (
    ComplianceDecision,
    RuleDefinition,
    RuleType,
    Severity,
    TradeCheckRequest,
    Violation,
)
from app.modules.compliance.models import ComplianceRuleRecord

if TYPE_CHECKING:
    from app.modules.compliance.pre_trade import PreTradeGate
    from app.modules.compliance.repository import (
        RuleRepository,
        ViolationRepository,
    )


def _to_rule(record: ComplianceRuleRecord) -> RuleDefinition:
    return RuleDefinition(
        id=UUID(record.id),
        name=record.name,
        rule_type=RuleType(record.rule_type),
        severity=Severity(record.severity),
        parameters=record.parameters,
        is_active=record.is_active,
        created_at=record.created_at,
    )


def _to_violation(record: object) -> Violation:
    from app.modules.compliance.models import (
        ComplianceViolationRecord,
    )

    assert isinstance(record, ComplianceViolationRecord)
    return Violation(
        id=UUID(record.id),
        portfolio_id=UUID(record.portfolio_id),
        rule_id=UUID(record.rule_id),
        rule_name=record.rule_name,
        severity=Severity(record.severity),
        message=record.message,
        current_value=record.current_value,
        limit_value=record.limit_value,
        detected_at=record.detected_at,
        resolved_at=record.resolved_at,
        resolved_by=record.resolved_by,
    )


class ComplianceService:
    """Orchestrates compliance rules, pre-trade checks, and violations."""

    def __init__(
        self,
        rule_repo: RuleRepository,
        violation_repo: ViolationRepository,
        pre_trade_gate: PreTradeGate,
    ) -> None:
        self._rule_repo = rule_repo
        self._violation_repo = violation_repo
        self._pre_trade_gate = pre_trade_gate

    # ---- Rules -------------------------------------------------------

    async def get_rules(self, fund_slug: str) -> list[RuleDefinition]:
        records = await self._rule_repo.get_active_by_fund(fund_slug)
        return [_to_rule(r) for r in records]

    async def create_rule(
        self,
        fund_slug: str,
        name: str,
        rule_type: RuleType,
        severity: Severity,
        parameters: dict[str, object],
    ) -> RuleDefinition:
        record = ComplianceRuleRecord(
            fund_slug=fund_slug,
            name=name,
            rule_type=rule_type.value,
            severity=severity.value,
            parameters=parameters,
            is_active=True,
        )
        saved = await self._rule_repo.insert(record)
        return _to_rule(saved)

    async def update_rule(
        self,
        rule_id: UUID,
        **fields: object,
    ) -> RuleDefinition:
        # Normalise enum values if present
        if "rule_type" in fields and isinstance(fields["rule_type"], RuleType):
            fields["rule_type"] = fields["rule_type"].value
        if "severity" in fields and isinstance(fields["severity"], Severity):
            fields["severity"] = fields["severity"].value

        record = await self._rule_repo.update(rule_id, **fields)
        if record is None:
            raise LookupError(f"Compliance rule {rule_id} not found")
        return _to_rule(record)

    # ---- Pre-trade check --------------------------------------------

    async def check_trade(
        self,
        request: TradeCheckRequest,
        fund_slug: str,
    ) -> ComplianceDecision:
        return await self._pre_trade_gate.check_trade(request, fund_slug)

    # ---- Violations --------------------------------------------------

    async def get_violations(self, portfolio_id: UUID) -> list[Violation]:
        records = await self._violation_repo.get_active_by_portfolio(portfolio_id)
        return [_to_violation(r) for r in records]

    async def resolve_violation(
        self,
        violation_id: UUID,
        resolved_by: str,
    ) -> Violation:
        record = await self._violation_repo.resolve(violation_id, resolved_by)
        if record is None:
            raise LookupError(f"Violation {violation_id} not found")
        return _to_violation(record)
