"""Smart order routing engine — selects broker(s) based on scorecards + rules.

When only one broker is registered (single-broker mode), routing is a
trivial pass-through with no scorecard evaluation. Multi-broker mode
scores available brokers and optionally splits large orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from app.modules.orders.models import RoutingDecisionRecord

if TYPE_CHECKING:
    from app.modules.orders.broker_registry import BrokerRegistry
    from app.modules.orders.interface import BrokerScorecard
    from app.modules.orders.routing_repository import RoutingRepository
    from app.modules.orders.scorecard_service import ScorecardService

logger = structlog.get_logger()

# Default scoring weights
_WEIGHTS = {
    "fill_rate": Decimal("0.30"),
    "slippage": Decimal("0.25"),
    "speed": Decimal("0.20"),
    "cost": Decimal("0.25"),
}


@dataclass(frozen=True)
class RoutingSlice:
    """One slice of a routed order — maps to one broker submission."""

    broker_id: str
    quantity: Decimal
    score: Decimal | None = None
    score_breakdown: dict[str, object] | None = None
    matched_rule_ids: list[str] | None = None
    reason: str = ""


class RoutingEngine:
    """Selects broker(s) for an order based on scorecards + configurable rules."""

    def __init__(
        self,
        *,
        broker_registry: BrokerRegistry,
        scorecard_service: ScorecardService,
        routing_repo: RoutingRepository,
        split_threshold: int = 50_000,
    ) -> None:
        self._registry = broker_registry
        self._scorecard_service = scorecard_service
        self._routing_repo = routing_repo
        self._split_threshold = split_threshold

    async def route_order(
        self,
        order_id: str,
        instrument_id: str,
        instrument_class: str | None,
        side: str,
        quantity: Decimal,
        order_type: str,
        fund_slug: str,
    ) -> list[RoutingSlice]:
        """Determine which broker(s) should handle this order.

        Returns a list of RoutingSlice. Usually length 1, but large
        orders may be split across multiple brokers.
        """
        broker_ids = self._registry.list_broker_ids()

        # Fast path: single broker mode
        if len(broker_ids) <= 1:
            broker_id = broker_ids[0] if broker_ids else "default"
            slice_ = RoutingSlice(
                broker_id=broker_id,
                quantity=quantity,
                reason="single broker mode",
            )
            await self._record_decision(order_id, slice_, fund_slug)
            return [slice_]

        # Check routing rules first (explicit preferences)
        rules = await self._routing_repo.get_rules_for_fund(
            fund_slug,
            instrument_class,
        )

        for rule in rules:
            if rule.preferred_broker_id not in broker_ids:
                continue
            if rule.min_size is not None and quantity < rule.min_size:
                continue
            if rule.max_size is not None and quantity > rule.max_size:
                continue
            # Rule matches — use preferred broker
            slice_ = RoutingSlice(
                broker_id=rule.preferred_broker_id,
                quantity=quantity,
                reason=f"routing rule {rule.id}",
                matched_rule_ids=[str(rule.id)],
            )
            await self._record_decision(order_id, slice_, fund_slug)
            return [slice_]

        # Score-based routing
        scored: list[tuple[str, Decimal, dict[str, object]]] = []
        for bid in broker_ids:
            scorecard = await self._scorecard_service.get_scorecard(
                bid,
                fund_slug,
                instrument_class,
            )
            score, breakdown = self._score_broker(scorecard, bid)
            scored.append((bid, score, breakdown))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Check if we should split across brokers
        if int(quantity) > self._split_threshold and len(scored) > 1:
            return await self._split_order(order_id, quantity, scored, fund_slug)

        # Single best broker
        best_id, best_score, best_breakdown = scored[0]
        slice_ = RoutingSlice(
            broker_id=best_id,
            quantity=quantity,
            score=best_score,
            score_breakdown=best_breakdown,
            reason="best scorecard",
        )
        await self._record_decision(order_id, slice_, fund_slug)
        return [slice_]

    def _score_broker(
        self,
        scorecard: BrokerScorecard | None,
        broker_id: str,
    ) -> tuple[Decimal, dict[str, object]]:
        """Compute composite score for a broker."""
        if scorecard is None:
            # No history — give a neutral score
            return Decimal("0.5"), {"fill_rate": 0.5, "slippage": 0.5, "speed": 0.5, "cost": 0.5}

        # Normalize each metric to 0-1 range
        fr = min(float(scorecard.fill_rate), 1.0)
        # Lower slippage is better: invert
        slip = max(0.0, 1.0 - float(scorecard.avg_slippage_bps) / 20.0)
        # Lower speed (ms) is better: 0ms=1.0, 200ms=0.0
        spd = max(0.0, 1.0 - scorecard.avg_fill_time_ms / 200.0)
        # Lower cost is better
        cst = max(0.0, 1.0 - float(scorecard.avg_cost_bps) / 20.0)

        breakdown: dict[str, object] = {
            "fill_rate": round(fr, 4),
            "slippage": round(slip, 4),
            "speed": round(spd, 4),
            "cost": round(cst, 4),
        }

        composite = (
            _WEIGHTS["fill_rate"] * Decimal(str(fr))
            + _WEIGHTS["slippage"] * Decimal(str(slip))
            + _WEIGHTS["speed"] * Decimal(str(spd))
            + _WEIGHTS["cost"] * Decimal(str(cst))
        )

        return composite.quantize(Decimal("0.000001")), breakdown

    async def _split_order(
        self,
        order_id: str,
        total_quantity: Decimal,
        scored: list[tuple[str, Decimal, dict[str, object]]],
        fund_slug: str,
    ) -> list[RoutingSlice]:
        """Split a large order proportionally across top brokers."""
        # Use top 2-3 brokers
        top_n = min(3, len(scored))
        top = scored[:top_n]

        total_score = sum(s for _, s, _ in top)
        if total_score == 0:
            total_score = Decimal("1")

        slices: list[RoutingSlice] = []
        remaining = total_quantity

        for i, (bid, score, breakdown) in enumerate(top):
            if i == top_n - 1:
                qty = remaining  # last slice gets the remainder
            else:
                qty = (total_quantity * score / total_score).quantize(Decimal("1"))
                qty = min(qty, remaining)
            remaining -= qty

            if qty <= 0:
                continue

            slice_ = RoutingSlice(
                broker_id=bid,
                quantity=qty,
                score=score,
                score_breakdown=breakdown,
                reason="order split proportional to scores",
            )
            slices.append(slice_)
            await self._record_decision(order_id, slice_, fund_slug)

        return slices

    async def _record_decision(
        self,
        order_id: str,
        slice_: RoutingSlice,
        fund_slug: str,
    ) -> None:
        """Persist routing decision for best execution audit trail."""
        try:
            record = RoutingDecisionRecord(
                id=str(uuid4()),
                order_id=order_id,
                broker_id=slice_.broker_id,
                quantity=slice_.quantity,
                score=slice_.score,
                score_breakdown=slice_.score_breakdown,
                rule_ids_matched=slice_.matched_rule_ids,
                decision_reason=slice_.reason,
                decided_at=datetime.now(UTC),
            )
            await self._routing_repo.save_decision(record)
        except Exception:
            logger.exception("routing_decision_save_failed", order_id=order_id)
