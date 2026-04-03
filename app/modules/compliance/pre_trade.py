"""Pre-trade compliance gate — fail-closed evaluation."""

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
    ComplianceDecision,
    EvaluationResult,
    RuleType,
    Severity,
    TradeCheckRequest,
)

if TYPE_CHECKING:
    from app.modules.compliance.repository import RuleRepository
    from app.modules.positions.interface import Position

logger = logging.getLogger(__name__)


def _build_position_info(pos: Position) -> PositionInfo:
    """Convert a Position value object to engine PositionInfo."""
    return PositionInfo(
        instrument_id=pos.instrument_id,
        quantity=pos.quantity,
        market_value=pos.market_value,
    )


class PreTradeGate:
    """Evaluates all active compliance rules against a hypothetical
    post-trade portfolio state.  Fail-closed: errors reject the trade.
    """

    def __init__(
        self,
        rule_repo: RuleRepository,
        position_service: object,
    ) -> None:
        self._rule_repo = rule_repo
        self._position_service = position_service

    async def check_trade(
        self,
        request: TradeCheckRequest,
        fund_slug: str,
    ) -> ComplianceDecision:
        try:
            return await self._evaluate(request, fund_slug)
        except Exception:
            logger.exception("Compliance check failed — rejecting trade (fail-closed)")
            return ComplianceDecision(
                approved=False,
                results=[
                    EvaluationResult(
                        rule_id=UUID(int=0),
                        rule_name="SYSTEM",
                        passed=False,
                        severity=Severity.BLOCK,
                        message=("Compliance check error — trade rejected (fail-closed)."),
                    )
                ],
                blocked_by=["SYSTEM"],
            )

    async def _evaluate(
        self,
        request: TradeCheckRequest,
        fund_slug: str,
    ) -> ComplianceDecision:
        from app.modules.compliance.interface import RuleDefinition

        # 1. Load active rules
        rule_records = await self._rule_repo.get_active_by_fund(fund_slug)
        if not rule_records:
            return ComplianceDecision(approved=True, results=[], blocked_by=[])

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

        # 2. Get current positions
        svc = self._position_service
        current_positions: list[Position] = (
            await svc.get_by_portfolio(request.portfolio_id)  # type: ignore[attr-defined]
        )

        # 3. Build hypothetical post-trade state
        state = self._build_hypothetical_state(request, current_positions)

        # 4. Evaluate all rules
        results: list[EvaluationResult] = []
        blocked_by: list[str] = []
        for rule in rules:
            evaluator = EVALUATOR_REGISTRY.get(RuleType(rule.rule_type))
            if evaluator is None:
                logger.warning(
                    "No evaluator for rule type %s",
                    rule.rule_type,
                )
                continue
            result = evaluator.evaluate(state, rule)
            results.append(result)
            if not result.passed and result.severity == Severity.BLOCK:
                blocked_by.append(rule.name)

        approved = len(blocked_by) == 0
        return ComplianceDecision(
            approved=approved,
            results=results,
            blocked_by=blocked_by,
        )

    def _build_hypothetical_state(
        self,
        request: TradeCheckRequest,
        current_positions: list[Position],
    ) -> PortfolioState:
        """Build a PortfolioState reflecting the post-trade world."""
        positions: dict[str, PositionInfo] = {}
        total_value = Decimal(0)

        for pos in current_positions:
            info = _build_position_info(pos)
            positions[pos.instrument_id] = info
            total_value += abs(pos.market_value)

        # Apply the proposed trade
        trade_value = request.quantity * request.price
        instrument = request.instrument_id.upper()

        if instrument in positions:
            existing = positions[instrument]
            if request.side.lower() == "buy":
                new_qty = existing.quantity + request.quantity
                new_mv = existing.market_value + trade_value
            else:
                new_qty = existing.quantity - request.quantity
                new_mv = existing.market_value - trade_value
            positions[instrument] = PositionInfo(
                instrument_id=instrument,
                quantity=new_qty,
                market_value=new_mv,
                asset_class=existing.asset_class,
                sector=existing.sector,
                country=existing.country,
            )
        else:
            sign = Decimal(1) if request.side.lower() == "buy" else Decimal(-1)
            positions[instrument] = PositionInfo(
                instrument_id=instrument,
                quantity=sign * request.quantity,
                market_value=sign * trade_value,
            )

        # Recalculate NAV
        nav = sum(abs(p.market_value) for p in positions.values())

        return PortfolioState(
            portfolio_id=request.portfolio_id,
            positions=positions,
            nav=Decimal(str(nav)),
        )
