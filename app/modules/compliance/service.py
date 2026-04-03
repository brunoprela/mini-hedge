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
    from app.modules.platform.audit_repository import AuditLogRepository


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
        audit_repo: AuditLogRepository | None = None,
    ) -> None:
        self._rule_repo = rule_repo
        self._violation_repo = violation_repo
        self._pre_trade_gate = pre_trade_gate
        self._audit = audit_repo

    @property
    def pre_trade_gate(self) -> PreTradeGate:
        """Public accessor for the pre-trade compliance gate."""
        return self._pre_trade_gate

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
        actor_id: str = "system",
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
        rule = _to_rule(saved)
        await self._audit_event(
            "compliance.rule.created",
            actor_id=actor_id,
            fund_slug=fund_slug,
            payload={"rule_id": str(rule.id), "name": name, "rule_type": rule_type.value},
        )
        return rule

    async def update_rule(
        self,
        rule_id: UUID,
        actor_id: str = "system",
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
        rule = _to_rule(record)
        await self._audit_event(
            "compliance.rule.updated",
            actor_id=actor_id,
            fund_slug=record.fund_slug,
            payload={"rule_id": str(rule_id), "changes": {k: str(v) for k, v in fields.items()}},
        )
        return rule

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
        violation = _to_violation(record)
        await self._audit_event(
            "compliance.violation.resolved",
            actor_id=resolved_by,
            fund_slug=None,
            payload={
                "violation_id": str(violation_id),
                "rule_name": violation.rule_name,
                "severity": violation.severity,
            },
        )
        return violation

    async def _audit_event(
        self,
        event_type: str,
        *,
        actor_id: str,
        fund_slug: str | None,
        payload: dict[str, object],
    ) -> None:
        if self._audit is None:
            return
        await self._audit.insert_admin_event(
            event_type=event_type,
            actor_id=actor_id,
            actor_type="user",
            fund_slug=fund_slug,
            payload=payload,
        )
