"""Compliance service — orchestrates rules, checks, and violations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.compliance.interface import (
    BreachType,
    ComplianceDecision,
    RemediationSuggestion,
    ResolutionType,
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
        grace_period_hours=record.grace_period_hours,
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
        breach_type=BreachType(record.breach_type),
        message=record.message,
        current_value=record.current_value,
        limit_value=record.limit_value,
        detected_at=record.detected_at,
        deadline_at=record.deadline_at,
        resolved_at=record.resolved_at,
        resolved_by=record.resolved_by,
        resolution_type=ResolutionType(record.resolution_type) if record.resolution_type else None,
    )


class ComplianceService:
    """Orchestrates compliance rules, pre-trade checks, and violations."""

    def __init__(
        self,
        rule_repo: RuleRepository,
        violation_repo: ViolationRepository,
        pre_trade_gate: PreTradeGate,
        audit_repo: AuditLogRepository | None = None,
        position_service: object | None = None,
        security_master: object | None = None,
    ) -> None:
        self._rule_repo = rule_repo
        self._violation_repo = violation_repo
        self._pre_trade_gate = pre_trade_gate
        self._audit = audit_repo
        self._position_service = position_service
        self._security_master = security_master

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
        resolution_type: str = "manual",
    ) -> Violation:
        record = await self._violation_repo.resolve(
            violation_id, resolved_by, resolution_type=resolution_type
        )
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
                "resolution_type": resolution_type,
            },
        )
        return violation

    async def waive_violation(
        self,
        violation_id: UUID,
        waived_by: str,
        reason: str,
    ) -> Violation:
        """Compliance officer grants a waiver for a violation."""
        record = await self._violation_repo.resolve(
            violation_id, waived_by, resolution_type="waived"
        )
        if record is None:
            raise LookupError(f"Violation {violation_id} not found")
        violation = _to_violation(record)
        await self._audit_event(
            "compliance.violation.waived",
            actor_id=waived_by,
            fund_slug=None,
            payload={
                "violation_id": str(violation_id),
                "rule_name": violation.rule_name,
                "severity": violation.severity,
                "reason": reason,
            },
        )
        return violation

    # ---- Remediation ----------------------------------------------------

    async def suggest_remediation(
        self,
        portfolio_id: UUID,
    ) -> list[RemediationSuggestion]:
        """Calculate trades needed to cure all active concentration violations.

        For each active concentration_limit violation, computes how many shares
        to sell to bring the position back under the limit with a 0.5% buffer.
        """
        from decimal import Decimal

        violations = await self._violation_repo.get_active_by_portfolio(portfolio_id)
        if not violations or self._position_service is None:
            return []

        # Load current positions
        positions = await self._position_service.get_by_portfolio(portfolio_id)  # type: ignore[attr-defined]
        if not positions:
            return []

        # Build position map and NAV
        pos_by_id: dict[str, object] = {}
        nav = Decimal(0)
        for pos in positions:
            pos_by_id[pos.instrument_id] = pos
            nav += abs(pos.market_value)

        if nav <= 0:
            return []

        suggestions: list[RemediationSuggestion] = []
        for v in violations:
            if v.limit_value is None or v.current_value is None:
                continue

            # Only handle concentration limits (single-name)
            # Parse the instrument from the violation message
            # Message format: "TICKER is X.XX% of NAV (limit Y%)"
            msg = v.message
            instrument_id = msg.split(" is ")[0] if " is " in msg else None
            if not instrument_id or instrument_id not in pos_by_id:
                continue

            pos = pos_by_id[instrument_id]
            current_mv = abs(pos.market_value)  # type: ignore[attr-defined]
            current_pct = (current_mv / nav) * 100
            limit_pct = v.limit_value

            # Target: bring to limit - 0.5% buffer to avoid immediate re-breach
            target_pct = limit_pct - Decimal("0.5")
            if target_pct < 0:
                target_pct = Decimal(0)

            target_mv = (target_pct / 100) * nav
            excess_mv = current_mv - target_mv
            if excess_mv <= 0:
                continue

            # Calculate shares to sell (use current price)
            price = pos.last_price if hasattr(pos, "last_price") and pos.last_price else None  # type: ignore[attr-defined]
            if price is None and pos.quantity != 0:  # type: ignore[attr-defined]
                price = current_mv / abs(pos.quantity)  # type: ignore[attr-defined]
            if price is None or price <= 0:
                continue

            qty_to_sell = (excess_mv / price).quantize(Decimal("1"))
            if qty_to_sell <= 0:
                continue

            suggestions.append(
                RemediationSuggestion(
                    violation_id=UUID(v.id),
                    rule_name=v.rule_name,
                    instrument_id=instrument_id,
                    side="sell",
                    quantity=qty_to_sell,
                    current_weight_pct=current_pct.quantize(Decimal("0.01")),
                    target_weight_pct=target_pct,
                    limit_pct=limit_pct,
                )
            )

        return suggestions

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
