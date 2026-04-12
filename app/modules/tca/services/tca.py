"""TCA orchestration — loads order data, computes VWAP, runs cost engine, persists."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.tca.core.cost_engine import CostEngine, TCAInput
from app.modules.tca.interfaces import (
    FundTCASummary,
    PortfolioTCAReport,
    TCAReport,
)
from app.modules.tca.models.tca_result import TCAResultRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.orders.models.order import OrderRecord
    from app.modules.orders.repositories import OrderRepository
    from app.modules.orders.services import ScorecardService
    from app.modules.tca.core.vwap import VWAPCalculator
    from app.modules.tca.repositories import TCARepository
    from app.shared.events import EventBus

logger = structlog.get_logger()

_ZERO = Decimal("0")
_DEFAULT_COMMISSION_BPS = Decimal("5")


class TCAService:
    """Orchestrates TCA computation for filled orders."""

    def __init__(
        self,
        *,
        tca_repo: TCARepository,
        order_repo: OrderRepository,
        vwap_calculator: VWAPCalculator,
        scorecard_service: ScorecardService | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._tca_repo = tca_repo
        self._order_repo = order_repo
        self._vwap = vwap_calculator
        self._scorecard_service = scorecard_service
        self._event_bus = event_bus

    async def compute_for_order(
        self,
        order_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> TCAReport | None:
        """Compute TCA for a filled order and persist the result.

        Returns None if the order is not eligible (not filled, no arrival price).
        """
        order = await self._order_repo.get_by_id(order_id, session=session)
        if order is None:
            logger.warning("tca_order_not_found", order_id=str(order_id))
            return None

        if order.state != "filled":
            logger.debug("tca_order_not_filled", order_id=str(order_id), state=order.state)
            return None

        if order.arrival_mid_price is None or order.arrival_mid_price <= 0:
            logger.warning("tca_no_arrival_price", order_id=str(order_id))
            return None

        # Load fills to determine execution window
        fills = await self._order_repo.get_fills(order_id, session=session)
        if not fills:
            logger.warning("tca_no_fills", order_id=str(order_id))
            return None

        execution_start = fills[0].filled_at
        execution_end = fills[-1].filled_at

        # Compute VWAP benchmark over execution window
        vwap = await self._vwap.compute(order.instrument_id, execution_start, execution_end)

        # Get commission rate from broker scorecard
        commission_bps = _DEFAULT_COMMISSION_BPS
        if self._scorecard_service and order.broker_id:
            sc = await self._scorecard_service.get_scorecard(order.broker_id, order.fund_slug)
            if sc is not None and sc.avg_cost_bps > 0:
                commission_bps = sc.avg_cost_bps

        # Get terminal price (latest price) for opportunity cost
        terminal_price: Decimal | None = None
        # Use the arrival price at order creation as the terminal reference
        # In a real system this would be the close price or current price

        # Build TCA input
        tca_input = TCAInput(
            side=order.side,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            avg_fill_price=order.avg_fill_price or _ZERO,
            arrival_mid_price=order.arrival_mid_price,
            arrival_spread=order.arrival_spread or _ZERO,
            vwap_benchmark=vwap,
            commission_rate_bps=commission_bps,
            adv=None,  # Could be enriched from security master
            execution_start=execution_start,
            execution_end=execution_end,
            terminal_price=terminal_price,
        )

        # Run pure computation
        result = CostEngine.compute(tca_input)

        # Persist
        record = TCAResultRecord(
            order_id=str(order_id),
            arrival_mid_price=order.arrival_mid_price,
            arrival_spread=order.arrival_spread or _ZERO,
            vwap_benchmark=vwap,
            total_cost_bps=result.total_cost_bps,
            commission_cost_bps=result.commission_cost_bps,
            spread_cost_bps=result.spread_cost_bps,
            market_impact_cost_bps=result.market_impact_cost_bps,
            timing_cost_bps=result.timing_cost_bps,
            opportunity_cost_bps=result.opportunity_cost_bps,
            implementation_shortfall_bps=result.implementation_shortfall_bps,
            participation_rate=result.participation_rate,
            execution_duration_seconds=result.execution_duration_seconds,
            total_cost_usd=result.total_cost_usd,
        )
        await self._tca_repo.save(record, session=session)

        logger.info(
            "tca_computed",
            order_id=str(order_id),
            total_cost_bps=str(result.total_cost_bps),
            impl_shortfall_bps=str(result.implementation_shortfall_bps),
        )

        if self._event_bus is not None:
            from app.shared.schema_registry import fund_topic

            await self._event_bus.publish(
                fund_topic(order.fund_slug, "tca.computed"),
                BaseEvent(
                    event_type=AuditEventType.TCA_COMPUTED,
                    data={
                        "order_id": str(order_id),
                        "instrument_id": order.instrument_id,
                        "total_cost_bps": str(result.total_cost_bps),
                        "implementation_shortfall_bps": str(result.implementation_shortfall_bps),
                    },
                    fund_slug=order.fund_slug,
                    actor_id="tca-service",
                ),
            )

        return self._to_report(order, record)

    async def get_for_order(
        self,
        order_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> TCAReport | None:
        """Retrieve previously computed TCA for an order."""
        order = await self._order_repo.get_by_id(order_id, session=session)
        if order is None:
            return None

        record = await self._tca_repo.get_by_order_id(order_id, session=session)
        if record is None:
            return None

        return self._to_report(order, record)

    async def get_portfolio_report(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> PortfolioTCAReport:
        """Aggregate TCA across all orders in a portfolio."""
        orders = await self._order_repo.get_by_portfolio(
            portfolio_id, state="filled", session=session
        )
        order_ids = [o.id for o in orders]
        tca_records = await self._tca_repo.get_by_order_ids(order_ids, session=session)
        tca_by_order = {r.order_id: r for r in tca_records}

        reports: list[TCAReport] = []
        for order in orders:
            record = tca_by_order.get(order.id)
            if record is not None:
                reports.append(self._to_report(order, record))

        n = len(reports) or 1
        return PortfolioTCAReport(
            portfolio_id=portfolio_id,
            total_orders=len(reports),
            avg_total_cost_bps=sum((r.total_cost_bps for r in reports), _ZERO) / n,
            avg_commission_bps=sum((r.commission_cost_bps for r in reports), _ZERO) / n,
            avg_spread_bps=sum((r.spread_cost_bps for r in reports), _ZERO) / n,
            avg_impact_bps=sum((r.market_impact_cost_bps for r in reports), _ZERO) / n,
            avg_timing_bps=sum((r.timing_cost_bps for r in reports), _ZERO) / n,
            total_cost_usd=sum((r.total_cost_usd for r in reports), _ZERO),
            orders=reports,
        )

    async def get_fund_summary(
        self,
        fund_slug: str,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> FundTCASummary:
        """High-level TCA summary for a fund over a time window.

        Scans all filled orders and their TCA records.
        """
        from sqlalchemy import select

        from app.modules.orders.models.order import OrderRecord

        async with self._order_repo._session(session) as s:
            stmt = select(OrderRecord).where(
                OrderRecord.fund_slug == fund_slug,
                OrderRecord.state == "filled",
                OrderRecord.updated_at >= start,
                OrderRecord.updated_at <= end,
            )
            result = await s.execute(stmt)
            orders = list(result.scalars().all())

        order_ids = [o.id for o in orders]
        tca_records = await self._tca_repo.get_by_order_ids(order_ids, session=session)

        n = len(tca_records) or 1
        return FundTCASummary(
            fund_slug=fund_slug,
            period_start=start,
            period_end=end,
            total_orders_analyzed=len(tca_records),
            avg_implementation_shortfall_bps=(
                sum((r.implementation_shortfall_bps for r in tca_records), _ZERO) / n
            ),
            avg_commission_bps=sum((r.commission_cost_bps for r in tca_records), _ZERO) / n,
            avg_spread_bps=sum((r.spread_cost_bps for r in tca_records), _ZERO) / n,
            avg_impact_bps=sum((r.market_impact_cost_bps for r in tca_records), _ZERO) / n,
            total_cost_usd=sum((r.total_cost_usd for r in tca_records), _ZERO),
        )

    @staticmethod
    def _to_report(order: OrderRecord, record: TCAResultRecord) -> TCAReport:
        return TCAReport(
            order_id=UUID(record.order_id),
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            avg_fill_price=order.avg_fill_price,
            arrival_mid_price=record.arrival_mid_price,
            arrival_spread=record.arrival_spread,
            vwap_benchmark=record.vwap_benchmark,
            total_cost_bps=record.total_cost_bps,
            commission_cost_bps=record.commission_cost_bps,
            spread_cost_bps=record.spread_cost_bps,
            market_impact_cost_bps=record.market_impact_cost_bps,
            timing_cost_bps=record.timing_cost_bps,
            opportunity_cost_bps=record.opportunity_cost_bps,
            implementation_shortfall_bps=record.implementation_shortfall_bps,
            participation_rate=record.participation_rate,
            execution_duration_seconds=record.execution_duration_seconds,
            total_cost_usd=record.total_cost_usd,
            computed_at=record.computed_at,
        )
