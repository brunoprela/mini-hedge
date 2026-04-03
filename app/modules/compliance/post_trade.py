"""Post-trade compliance monitor — evaluates actual portfolio state.

Subscribes to ``positions.changed`` events and evaluates all active
compliance rules against the actual (not hypothetical) portfolio.
Violations are persisted and published as events.
"""

from __future__ import annotations

import logging
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

if TYPE_CHECKING:
    from app.modules.positions.interface import Position
    from app.modules.security_master.service import SecurityMasterService
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent

logger = logging.getLogger(__name__)


class PostTradeMonitor:
    """Evaluates actual portfolio against compliance rules on position changes.

    Subscribes to ``positions.changed`` events. When a position changes,
    loads the full portfolio, evaluates all rules, and persists any new
    violations.
    """

    def __init__(
        self,
        session_factory: TenantSessionFactory,
        position_service: object,
        security_master: SecurityMasterService | None = None,
    ) -> None:
        self._sf = session_factory
        self._position_service = position_service
        self._sm = security_master

    async def handle_position_changed(self, event: BaseEvent) -> None:
        """Event handler for ``positions.changed`` topic."""
        try:
            data = event.data
            portfolio_id_str = data.get("portfolio_id")
            fund_slug = event.fund_slug
            if not portfolio_id_str or not fund_slug:
                return

            portfolio_id = UUID(str(portfolio_id_str))
            await self._evaluate_portfolio(portfolio_id, fund_slug)
        except Exception:
            logger.exception(
                "post_trade_monitor_failed",
                extra={"event_id": event.event_id},
            )

    async def _evaluate_portfolio(
        self,
        portfolio_id: UUID,
        fund_slug: str,
    ) -> None:
        """Load portfolio, evaluate rules, persist violations."""
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
                created_at=r.created_at,
            )
            for r in rule_records
        ]

        # Load current positions
        positions: list[Position] = await self._position_service.get_by_portfolio(  # type: ignore[attr-defined]
            portfolio_id
        )
        if not positions:
            return

        # Build actual portfolio state
        state = await self._build_actual_state(portfolio_id, positions)

        # Evaluate all rules
        # Load existing active violations to avoid duplicates
        existing = await violation_repo.get_active_by_portfolio(portfolio_id)
        existing_rule_ids = {v.rule_id for v in existing}

        for rule in rules:
            evaluator = EVALUATOR_REGISTRY.get(RuleType(rule.rule_type))
            if evaluator is None:
                continue

            result = evaluator.evaluate(state, rule)
            if not result.passed and str(rule.id) not in existing_rule_ids:
                # New violation — persist it
                record = ComplianceViolationRecord(
                    portfolio_id=str(portfolio_id),
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=result.message,
                    current_value=result.current_value,
                    limit_value=result.limit_value,
                )
                await violation_repo.insert(record)
                logger.info(
                    "compliance_violation_detected",
                    portfolio_id=str(portfolio_id),
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=result.message,
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
