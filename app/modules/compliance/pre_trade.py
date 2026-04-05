"""Pre-trade compliance gate — fail-closed evaluation."""

from __future__ import annotations

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
    RuleDefinition,
    RuleType,
    Severity,
    TradeCheckRequest,
)

if TYPE_CHECKING:
    from app.modules.cash_management.repository import CashBalanceRepository
    from app.modules.compliance.repository import RuleRepository
    from app.modules.positions.interface import Position
    from app.modules.positions.service import PositionService
    from app.modules.security_master.service import SecurityMasterService

import structlog

logger = structlog.get_logger()


class PreTradeGate:
    """Evaluates all active compliance rules against a hypothetical
    post-trade portfolio state.  Fail-closed: errors reject the trade.
    """

    def __init__(
        self,
        *,
        rule_repo: RuleRepository,
        position_service: PositionService,
        security_master: SecurityMasterService | None = None,
        cash_balance_repo: CashBalanceRepository | None = None,
    ) -> None:
        self._rule_repo = rule_repo
        self._position_service = position_service
        self._security_master_service = security_master
        self._cash_balance_repo = cash_balance_repo

    async def check_trade(
        self,
        request: TradeCheckRequest,
    ) -> ComplianceDecision:
        try:
            return await self._evaluate(request)
        except Exception:
            logger.exception("compliance_check_failed")
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
    ) -> ComplianceDecision:
        # 1. Load active rules (session is already fund-scoped)
        rule_records = await self._rule_repo.get_active()
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
        current_positions: list[Position] = await self._position_service.get_by_portfolio(
            request.portfolio_id
        )

        # 3. Build hypothetical post-trade state
        state = await self._build_hypothetical_state(request, current_positions)

        # 4. Evaluate all rules
        results: list[EvaluationResult] = []
        blocked_by: list[str] = []
        for rule in rules:
            evaluator = EVALUATOR_REGISTRY.get(RuleType(rule.rule_type))
            if evaluator is None:
                logger.warning(
                    "no_evaluator_for_rule_type",
                    rule_type=rule.rule_type,
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

    async def _lookup_instrument_metadata(
        self,
        instrument_id: str,
    ) -> tuple[str, str, str]:
        """Look up asset_class, sector, country for an instrument.

        Returns defaults if security master is unavailable.
        """
        if self._security_master_service is None:
            return ("", "", "")
        try:
            inst = await self._security_master_service.get_by_ticker(instrument_id)
            return (
                str(inst.asset_class) if inst.asset_class else "",
                inst.sector or "",
                inst.country or "",
            )
        except Exception:
            return ("", "", "")

    async def _build_hypothetical_state(
        self,
        request: TradeCheckRequest,
        current_positions: list[Position],
    ) -> PortfolioState:
        """Build a PortfolioState reflecting the post-trade world."""
        positions: dict[str, PositionInfo] = {}
        total_value = Decimal(0)

        # Look up metadata for all instruments (current + traded)
        instrument_ids = {pos.instrument_id for pos in current_positions}
        instrument_ids.add(request.instrument_id.upper())

        metadata_cache: dict[str, tuple[str, str, str]] = {}
        for iid in instrument_ids:
            metadata_cache[iid] = await self._lookup_instrument_metadata(iid)

        for pos in current_positions:
            asset_class, sector, country = metadata_cache.get(pos.instrument_id, ("", "", ""))
            info = PositionInfo(
                instrument_id=pos.instrument_id,
                quantity=pos.quantity,
                market_value=pos.market_value,
                asset_class=asset_class,
                sector=sector,
                country=country,
            )
            positions[pos.instrument_id] = info
            total_value += abs(pos.market_value)

        # Apply the proposed trade
        trade_value = request.quantity * request.price
        instrument = request.instrument_id.upper()
        asset_class, sector, country = metadata_cache.get(instrument, ("", "", ""))

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
                asset_class=asset_class,
                sector=sector,
                country=country,
            )

        # Recalculate NAV: positions + available cash
        position_value = sum(abs(p.market_value) for p in positions.values())
        cash = Decimal(0)
        if self._cash_balance_repo is not None:
            balances = await self._cash_balance_repo.get_by_portfolio(request.portfolio_id)
            cash = sum(b.available_balance for b in balances)
        nav = position_value + cash

        return PortfolioState(
            portfolio_id=request.portfolio_id,
            positions=positions,
            nav=Decimal(str(nav)),
        )
