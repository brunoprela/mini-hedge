"""Alpha engine service — what-if analysis, optimization, order intents."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import numpy as np
import structlog

from app.modules.alpha_engine.core.calculator import (
    optimize_portfolio,
    run_what_if,
)
from app.modules.alpha_engine.interfaces import (
    HypotheticalTrade,
    OptimizationObjective,
    OptimizationResult,
    OptimizationWeight,
    OrderIntent,
    ScenarioRun,
    ScenarioStatus,
    WhatIfResult,
)
from app.modules.alpha_engine.models.optimization_run import OptimizationRunRecord
from app.modules.alpha_engine.models.optimization_weight import OptimizationWeightRecord
from app.modules.alpha_engine.models.order_intent import OrderIntentRecord
from app.modules.alpha_engine.models.scenario_run import ScenarioRunRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.alpha_engine.repositories import (
        OptimizationRunRepository,
        OptimizationWeightRepository,
        OrderIntentRepository,
        ScenarioRunRepository,
    )
    from app.modules.positions.services import PositionService
    from app.modules.security_master.services import SecurityMasterService
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)


class AlphaService:
    """What-if analysis, portfolio optimization, and order intent generation."""

    def __init__(
        self,
        *,
        scenario_repo: ScenarioRunRepository,
        opt_run_repo: OptimizationRunRepository,
        opt_weight_repo: OptimizationWeightRepository,
        intent_repo: OrderIntentRepository,
        position_service: PositionService,
        security_master_service: SecurityMasterService,
        event_bus: EventBus | None = None,
    ) -> None:
        self._scenario_repo = scenario_repo
        self._opt_run_repo = opt_run_repo
        self._opt_weight_repo = opt_weight_repo
        self._intent_repo = intent_repo
        self._position_service = position_service
        self._security_master_service = security_master_service
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # What-if analysis
    # ------------------------------------------------------------------

    async def run_what_if(
        self,
        portfolio_id: UUID,
        scenario_name: str,
        trades: list[HypotheticalTrade],
        *,
        session: AsyncSession | None = None,
    ) -> WhatIfResult:
        """Run a what-if scenario analysis."""
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        positions = [p for p in positions if p.quantity != ZERO]

        nav = float(sum((p.market_value for p in positions if p.market_value), ZERO))

        current_positions: dict[str, tuple[Decimal, Decimal]] = {}
        prices: dict[str, Decimal] = {}

        for p in positions:
            current_positions[p.instrument_id] = (
                p.quantity,
                p.market_value or ZERO,
            )
            if p.quantity != ZERO and p.market_value:
                prices[p.instrument_id] = p.market_value / p.quantity

        # Also add prices for instruments in trades but not in portfolio
        for trade in trades:
            if trade.instrument_id not in prices:
                prices[trade.instrument_id] = trade.price

        result = run_what_if(
            portfolio_id,
            scenario_name,
            current_positions,
            trades,
            prices,
            nav,
        )

        # Persist scenario run
        await self._persist_scenario(portfolio_id, scenario_name, trades, result, session=session)

        logger.info(
            "what_if_completed",
            portfolio_id=str(portfolio_id),
            scenario=scenario_name,
            nav_change=str(result.nav_change_pct),
        )
        return result

    # ------------------------------------------------------------------
    # Portfolio optimization
    # ------------------------------------------------------------------

    async def optimize(
        self,
        portfolio_id: UUID,
        objective: OptimizationObjective,
        *,
        session: AsyncSession | None = None,
    ) -> OptimizationResult:
        """Run portfolio optimization."""
        positions = await self._position_service.get_by_portfolio(portfolio_id, session=session)
        positions = [p for p in positions if p.quantity != ZERO]

        if not positions:
            return OptimizationResult(
                portfolio_id=portfolio_id,
                objective=objective,
                expected_return=ZERO,
                expected_risk=ZERO,
                weights=[],
                order_intents=[],
                calculated_at=datetime.now(UTC),
            )

        nav = float(sum((p.market_value for p in positions if p.market_value), ZERO))
        instrument_ids = [p.instrument_id for p in positions]

        current_weights = {
            p.instrument_id: float(p.market_value) / nav
            for p in positions
            if p.market_value and nav > 0
        }

        prices_map: dict[str, float] = {}
        for p in positions:
            if p.quantity != ZERO and p.market_value:
                prices_map[p.instrument_id] = float(p.market_value / p.quantity)

        # Build returns matrix
        returns_matrix = await self._build_returns_matrix(instrument_ids, session=session)

        result = optimize_portfolio(
            portfolio_id,
            objective,
            current_weights,
            returns_matrix,
            instrument_ids,
            prices_map,
            nav,
        )

        # Persist
        await self._persist_optimization(result, session=session)

        logger.info(
            "optimization_completed",
            portfolio_id=str(portfolio_id),
            objective=objective,
            sharpe=str(result.sharpe_ratio),
            intents=len(result.order_intents),
        )
        if result.order_intents:
            await self._publish_intents_event(portfolio_id, result)
        return result

    # ------------------------------------------------------------------
    # Scenario history
    # ------------------------------------------------------------------

    async def get_scenarios(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[ScenarioRun]:
        records = await self._scenario_repo.list_by_portfolio(portfolio_id, session=session)
        return [
            ScenarioRun(
                id=UUID(r.id),
                portfolio_id=UUID(r.portfolio_id),
                scenario_name=r.scenario_name,
                trades=r.trades if isinstance(r.trades, list) else [],
                result_summary=r.result_summary,
                status=ScenarioStatus(r.status),
                created_at=r.created_at,
            )
            for r in records
        ]

    # ------------------------------------------------------------------
    # Order intents
    # ------------------------------------------------------------------

    async def get_order_intents(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[OrderIntent]:
        records = await self._intent_repo.get_by_portfolio(portfolio_id, session=session)
        return [
            OrderIntent(
                instrument_id=r.instrument_id,
                side=r.side,
                quantity=Decimal(r.quantity),
                estimated_value=r.estimated_value,
                reason=r.reason,
            )
            for r in records
        ]

    async def approve_intent(self, intent_id: str, *, session: AsyncSession | None = None) -> None:
        await self._intent_repo.update_status(intent_id, "approved", session=session)

    async def cancel_intent(self, intent_id: str, *, session: AsyncSession | None = None) -> None:
        await self._intent_repo.update_status(intent_id, "cancelled", session=session)

    # ------------------------------------------------------------------
    # Optimization history
    # ------------------------------------------------------------------

    async def get_optimizations(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[OptimizationResult]:
        records = await self._opt_run_repo.list_by_portfolio(portfolio_id, session=session)
        results = []
        for r in records:
            weight_records = await self._opt_weight_repo.get_by_run(r.id, session=session)
            intent_records = await self._intent_repo.get_by_run(r.id, session=session)

            weights = [
                OptimizationWeight(
                    instrument_id=w.instrument_id,
                    current_weight=w.current_weight,
                    target_weight=w.target_weight,
                    delta_weight=w.delta_weight,
                    delta_shares=w.delta_shares,
                    delta_value=w.delta_value,
                )
                for w in weight_records
            ]

            intents = [
                OrderIntent(
                    instrument_id=i.instrument_id,
                    side=i.side,
                    quantity=Decimal(i.quantity),
                    estimated_value=i.estimated_value,
                    reason=i.reason,
                )
                for i in intent_records
            ]

            results.append(
                OptimizationResult(
                    id=UUID(r.id) if r.id else None,
                    portfolio_id=UUID(r.portfolio_id),
                    objective=OptimizationObjective(r.objective),
                    expected_return=r.expected_return,
                    expected_risk=r.expected_risk,
                    sharpe_ratio=r.sharpe_ratio,
                    weights=weights,
                    order_intents=intents,
                    calculated_at=r.created_at,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _publish_intents_event(
        self,
        portfolio_id: UUID,
        result: OptimizationResult,
    ) -> None:
        if self._event_bus is None:
            return
        from app.shared.database import TenantSessionFactory

        fund_slug = TenantSessionFactory.current_fund_slug()
        if not fund_slug:
            return
        event = BaseEvent(
            event_type=AuditEventType.ORDER_INTENTS_GENERATED,
            data={
                "portfolio_id": str(portfolio_id),
                "objective": str(result.objective),
                "intent_count": len(result.order_intents),
                "intents": [
                    {
                        "instrument_id": i.instrument_id,
                        "side": i.side,
                        "quantity": str(i.quantity),
                    }
                    for i in result.order_intents
                ],
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(
            fund_topic(fund_slug, "order_intents.generated"), event
        )

    async def _build_returns_matrix(
        self,
        instrument_ids: list[str],
        n_days: int = 252,
        *,
        session: AsyncSession | None = None,
    ) -> np.ndarray:
        """Build synthetic returns matrix from instrument reference data."""
        instruments = await self._security_master_service.list_active(session=session)
        vol_map = {
            i.ticker: i.annual_volatility for i in instruments if i.annual_volatility is not None
        }
        drift_map = {i.ticker: i.annual_drift for i in instruments if i.annual_drift is not None}

        n = len(instrument_ids)
        matrix = np.zeros((n_days, n))
        for i, iid in enumerate(instrument_ids):
            daily_vol = vol_map.get(iid, 0.25) / np.sqrt(252)
            daily_drift = drift_map.get(iid, 0.08) / 252
            matrix[:, i] = np.random.normal(daily_drift, daily_vol, n_days)
        return matrix

    async def _persist_scenario(
        self,
        portfolio_id: UUID,
        scenario_name: str,
        trades: list[HypotheticalTrade],
        result: WhatIfResult,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        record = ScenarioRunRecord(
            portfolio_id=str(portfolio_id),
            scenario_name=scenario_name,
            trades=[
                {
                    "instrument_id": t.instrument_id,
                    "side": t.side,
                    "quantity": str(t.quantity),
                    "price": str(t.price),
                }
                for t in trades
            ],
            result_summary={
                "current_nav": str(result.current_nav),
                "proposed_nav": str(result.proposed_nav),
                "nav_change_pct": str(result.nav_change_pct),
            },
            status="completed",
        )
        await self._scenario_repo.insert(record, session=session)

    async def _persist_optimization(
        self, result: OptimizationResult, *, session: AsyncSession | None = None
    ) -> None:
        opt_id = str(uuid4())
        record = OptimizationRunRecord(
            id=opt_id,
            portfolio_id=str(result.portfolio_id),
            objective=result.objective,
            expected_return=result.expected_return,
            expected_risk=result.expected_risk,
            sharpe_ratio=result.sharpe_ratio,
        )

        weights = [
            OptimizationWeightRecord(
                optimization_run_id=record.id,
                instrument_id=w.instrument_id,
                current_weight=w.current_weight,
                target_weight=w.target_weight,
                delta_weight=w.delta_weight,
                delta_shares=w.delta_shares,
                delta_value=w.delta_value,
            )
            for w in result.weights
        ]

        intents = [
            OrderIntentRecord(
                optimization_run_id=record.id,
                portfolio_id=str(result.portfolio_id),
                instrument_id=i.instrument_id,
                side=i.side,
                quantity=round(i.quantity),
                estimated_value=i.estimated_value,
                reason=i.reason,
            )
            for i in result.order_intents
        ]

        await self._opt_run_repo.insert(record, session=session)
        await self._opt_weight_repo.insert_batch(weights, session=session)
        await self._intent_repo.insert_batch(intents, session=session)
