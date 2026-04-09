"""Best execution reporting — regulatory audit trail for MiFID II / SEC Rule 606.

Generates reports showing routing decisions, execution quality per broker,
and comparison of achieved vs available prices.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.modules.orders.interfaces import BestExecutionReport

if TYPE_CHECKING:
    from app.modules.orders.routing.repositories import RoutingRepository
    from app.modules.orders.scorecard.services import ScorecardService


class BestExecutionService:
    """Generates best execution reports for regulatory compliance."""

    def __init__(
        self,
        *,
        routing_repo: RoutingRepository,
        scorecard_service: ScorecardService,
    ) -> None:
        self._routing_repo = routing_repo
        self._scorecard_service = scorecard_service

    async def generate_report(
        self,
        fund_slug: str,
        start_date: datetime,
        end_date: datetime,
    ) -> BestExecutionReport:
        """Generate a best execution report for a date range."""
        decisions = await self._routing_repo.get_decisions_in_range(
            start_date,
            end_date,
        )

        # Aggregate by broker
        broker_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"orders": 0, "total_quantity": Decimal("0"), "avg_score": Decimal("0")},
        )
        total_slippage = Decimal("0")
        total_cost = Decimal("0")

        for d in decisions:
            stats = broker_stats[d.broker_id]
            stats["orders"] += 1
            stats["total_quantity"] += d.quantity
            if d.score is not None:
                stats["avg_score"] += d.score

        broker_breakdown = []
        for broker_id, stats in broker_stats.items():
            if stats["orders"] > 0:
                stats["avg_score"] = (stats["avg_score"] / stats["orders"]).quantize(
                    Decimal("0.0001")
                )
            broker_breakdown.append(
                {
                    "broker_id": broker_id,
                    "order_count": stats["orders"],
                    "total_quantity": str(stats["total_quantity"]),
                    "avg_routing_score": str(stats["avg_score"]),
                }
            )

        # Get current scorecards for context
        scorecards = await self._scorecard_service.get_all_scorecards(fund_slug)
        for sc in scorecards:
            for entry in broker_breakdown:
                if entry["broker_id"] == sc.broker_id:
                    entry["fill_rate"] = str(sc.fill_rate)
                    entry["avg_slippage_bps"] = str(sc.avg_slippage_bps)
                    entry["avg_cost_bps"] = str(sc.avg_cost_bps)
                    total_slippage += sc.avg_slippage_bps
                    total_cost += sc.avg_cost_bps

        n = max(len(scorecards), 1)
        return BestExecutionReport(
            fund_slug=fund_slug,
            period_start=start_date,
            period_end=end_date,
            total_orders=len(decisions),
            broker_breakdown=broker_breakdown,
            avg_slippage_bps=(total_slippage / n).quantize(Decimal("0.0001")),
            avg_cost_bps=(total_cost / n).quantize(Decimal("0.0001")),
        )

    async def get_order_execution_detail(
        self,
        order_id: UUID,
        fund_slug: str,
    ) -> dict[str, object]:
        """Detailed execution analysis for a single order."""
        decisions = await self._routing_repo.get_decisions_for_order(order_id)
        return {
            "order_id": str(order_id),
            "routing_decisions": [
                {
                    "broker_id": d.broker_id,
                    "quantity": str(d.quantity),
                    "score": str(d.score) if d.score else None,
                    "score_breakdown": d.score_breakdown,
                    "rule_ids_matched": d.rule_ids_matched,
                    "decision_reason": d.decision_reason,
                    "decided_at": d.decided_at.isoformat(),
                }
                for d in decisions
            ],
        }
