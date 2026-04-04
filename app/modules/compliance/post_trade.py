"""Post-trade compliance monitor — evaluates actual portfolio state.

Subscribes to ``positions.changed`` events and evaluates all active
compliance rules against the actual (not hypothetical) portfolio.

Key behaviors:
- Detects new violations and persists them
- Auto-resolves violations when the portfolio drifts back into compliance
- Distinguishes active (trade-caused) vs passive (market-drift) breaches
- Sets cure deadlines based on rule grace periods
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.compliance.engine import (
    EVALUATOR_REGISTRY,
    PortfolioState,
    PositionInfo,
)
from app.modules.compliance.interface import (
    RuleDefinition,
    RuleType,
    Severity,
)
from app.modules.compliance.models import ComplianceViolationRecord

from app.modules.positions.interface import Position

if TYPE_CHECKING:
    from app.modules.security_master.service import SecurityMasterService
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus

logger = logging.getLogger(__name__)


class PostTradeMonitor:
    """Evaluates actual portfolio against compliance rules on position changes.

    Subscribes to ``positions.changed`` events. When a position changes,
    loads the full portfolio, evaluates all rules, and:
    - Creates new violations for newly breached rules
    - Auto-resolves existing violations for rules that now pass
    """

    def __init__(
        self,
        session_factory: TenantSessionFactory,
        position_service: object,
        security_master: SecurityMasterService | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._sf = session_factory
        self._position_service = position_service
        self._sm = security_master
        self._event_bus = event_bus

    async def handle_position_changed(self, event: BaseEvent) -> None:
        """Event handler for ``positions.changed`` topic (trade-triggered)."""
        try:
            data = event.data
            portfolio_id_str = data.get("portfolio_id")
            fund_slug = event.fund_slug
            if not portfolio_id_str or not fund_slug:
                return

            portfolio_id = UUID(str(portfolio_id_str))
            await self._evaluate_portfolio(portfolio_id, fund_slug, is_passive=False)
        except Exception:
            logger.exception(
                "post_trade_monitor_failed",
                extra={"event_id": event.event_id},
            )

    async def handle_mtm_update(self, event: BaseEvent) -> None:
        """Event handler for ``pnl.updated`` topic (price-drift-triggered).

        Detects passive breaches caused by market movements and auto-resolves
        violations when prices drift back into compliance.
        """
        try:
            data = event.data
            portfolio_id_str = data.get("portfolio_id")
            fund_slug = event.fund_slug
            if not portfolio_id_str or not fund_slug:
                return

            portfolio_id = UUID(str(portfolio_id_str))
            await self._evaluate_portfolio(portfolio_id, fund_slug, is_passive=True)
        except Exception:
            logger.exception(
                "post_trade_monitor_mtm_failed",
                extra={"event_id": event.event_id},
            )

    async def _evaluate_portfolio(
        self,
        portfolio_id: UUID,
        fund_slug: str,
        *,
        is_passive: bool = False,
    ) -> None:
        """Load portfolio, evaluate rules, persist/resolve violations."""
        from app.modules.compliance.repository import (
            RuleRepository,
            ViolationRepository,
        )

        rule_repo = RuleRepository(self._sf, fund_slug=fund_slug)
        violation_repo = ViolationRepository(self._sf, fund_slug=fund_slug)

        # Load active rules
        rule_records = await rule_repo.get_active_by_fund(fund_slug)
        if not rule_records:
            return

        rules: list[RuleDefinition] = [
            RuleDefinition(
                id=UUID(r.id),
                name=r.name,
                rule_type=RuleType(r.rule_type),
                severity=Severity(r.severity),
                parameters=r.parameters,
                is_active=r.is_active,
                grace_period_hours=r.grace_period_hours,
                created_at=r.created_at,
            )
            for r in rule_records
        ]

        # Load current positions (use fund-scoped repo, not the shared
        # position_service, because we're running outside request context)
        from app.modules.positions.position_repository import CurrentPositionRepository

        pos_repo = CurrentPositionRepository(self._sf, fund_slug=fund_slug)
        pos_records = await pos_repo.get_by_portfolio(portfolio_id)
        positions: list[Position] = [
            Position(
                portfolio_id=UUID(r.portfolio_id),
                instrument_id=r.instrument_id,
                quantity=r.quantity,
                avg_cost=r.avg_cost,
                cost_basis=r.cost_basis,
                market_price=r.market_price,
                market_value=r.market_value,
                unrealized_pnl=r.unrealized_pnl,
                currency=r.currency,
                last_updated=r.last_updated,
            )
            for r in pos_records
        ]
        if not positions:
            return

        # Build actual portfolio state
        state = await self._build_actual_state(portfolio_id, positions)

        # Load existing active violations
        existing = await violation_repo.get_active_by_portfolio(portfolio_id)
        existing_by_rule_id: dict[str, ComplianceViolationRecord] = {
            v.rule_id: v for v in existing
        }

        for rule in rules:
            evaluator = EVALUATOR_REGISTRY.get(RuleType(rule.rule_type))
            if evaluator is None:
                continue

            result = evaluator.evaluate(state, rule)
            rule_id_str = str(rule.id)

            if not result.passed and rule_id_str not in existing_by_rule_id:
                # New violation — persist it
                breach_type = "passive" if is_passive else "active"
                deadline_at = None
                if rule.grace_period_hours and is_passive:
                    deadline_at = datetime.now(UTC) + timedelta(hours=rule.grace_period_hours)

                record = ComplianceViolationRecord(
                    portfolio_id=str(portfolio_id),
                    rule_id=rule_id_str,
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=result.message,
                    current_value=result.current_value,
                    limit_value=result.limit_value,
                    breach_type=breach_type,
                    deadline_at=deadline_at,
                )
                await violation_repo.insert(record)
                await self._publish_violation(record, portfolio_id, fund_slug)
                logger.info(
                    "compliance_violation_detected",
                    portfolio_id=str(portfolio_id),
                    rule_name=rule.name,
                    severity=rule.severity,
                    breach_type=breach_type,
                    message=result.message,
                )

            elif result.passed and rule_id_str in existing_by_rule_id:
                # Rule now passes — auto-resolve the existing violation
                violation = existing_by_rule_id[rule_id_str]
                await violation_repo.resolve(
                    UUID(violation.id),
                    resolved_by="system",
                    resolution_type="auto",
                )
                await self._publish_violation_resolved(
                    violation, portfolio_id, fund_slug
                )
                logger.info(
                    "compliance_violation_auto_resolved",
                    portfolio_id=str(portfolio_id),
                    rule_name=rule.name,
                    violation_id=violation.id,
                )

    async def _publish_violation(
        self,
        record: ComplianceViolationRecord,
        portfolio_id: UUID,
        fund_slug: str,
    ) -> None:
        """Publish a compliance violation event to Kafka."""
        if self._event_bus is None:
            return
        from app.shared.events import BaseEvent
        from app.shared.schema_registry import fund_topic

        event = BaseEvent(
            event_type="compliance.violation",
            data={
                "violation_id": record.id,
                "portfolio_id": str(portfolio_id),
                "rule_id": record.rule_id,
                "rule_name": record.rule_name,
                "severity": record.severity,
                "breach_type": record.breach_type,
                "message": record.message,
                "current_value": str(record.current_value),
                "limit_value": str(record.limit_value),
                "deadline_at": record.deadline_at.isoformat() if record.deadline_at else None,
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(
            fund_topic(fund_slug, "compliance.violations"),
            event,
        )

    async def _publish_violation_resolved(
        self,
        record: ComplianceViolationRecord,
        portfolio_id: UUID,
        fund_slug: str,
    ) -> None:
        """Publish a violation resolved event to Kafka."""
        if self._event_bus is None:
            return
        from app.shared.events import BaseEvent
        from app.shared.schema_registry import fund_topic

        event = BaseEvent(
            event_type="compliance.violation.resolved",
            data={
                "violation_id": record.id,
                "portfolio_id": str(portfolio_id),
                "rule_id": record.rule_id,
                "rule_name": record.rule_name,
                "severity": record.severity,
                "message": f"Auto-resolved: {record.rule_name}",
                "current_value": str(record.current_value or 0),
                "limit_value": str(record.limit_value or 0),
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(
            fund_topic(fund_slug, "compliance.violations"),
            event,
        )

    async def _lookup_instrument_metadata(
        self,
        instrument_id: str,
    ) -> tuple[str, str, str]:
        if self._sm is None:
            return ("", "", "")
        try:
            inst = await self._sm.get_by_ticker(instrument_id)
            return (
                str(inst.asset_class) if inst.asset_class else "",
                inst.sector or "",
                inst.country or "",
            )
        except Exception:
            return ("", "", "")

    async def _build_actual_state(
        self,
        portfolio_id: UUID,
        positions: list[Position],
    ) -> PortfolioState:
        """Build PortfolioState from actual current positions."""
        pos_map: dict[str, PositionInfo] = {}

        for pos in positions:
            asset_class, sector, country = await self._lookup_instrument_metadata(pos.instrument_id)
            pos_map[pos.instrument_id] = PositionInfo(
                instrument_id=pos.instrument_id,
                quantity=pos.quantity,
                market_value=pos.market_value,
                asset_class=asset_class,
                sector=sector,
                country=country,
            )

        nav = sum(abs(p.market_value) for p in pos_map.values())

        return PortfolioState(
            portfolio_id=portfolio_id,
            positions=pos_map,
            nav=Decimal(str(nav)),
        )
