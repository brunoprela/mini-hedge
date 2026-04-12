"""Unit tests for BestExecutionService — report generation and order detail."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.orders.core.best_execution import BestExecutionService
from app.modules.orders.interfaces import BrokerScorecard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_routing_decision(
    broker_id: str = "broker-1",
    quantity: Decimal = Decimal("100"),
    score: Decimal | None = Decimal("0.85"),
    score_breakdown: dict | None = None,
    rule_ids_matched: dict | None = None,
    decision_reason: str | None = "best_score",
) -> MagicMock:
    d = MagicMock()
    d.broker_id = broker_id
    d.quantity = quantity
    d.score = score
    d.score_breakdown = score_breakdown or {"fill_rate": 0.9}
    d.rule_ids_matched = rule_ids_matched or ["rule-1"]
    d.decision_reason = decision_reason
    d.decided_at = datetime.now(UTC)
    return d


def _make_scorecard(
    broker_id: str = "broker-1",
    fill_rate: Decimal = Decimal("0.95"),
    avg_slippage_bps: Decimal = Decimal("1.5"),
    avg_cost_bps: Decimal = Decimal("3.0"),
) -> BrokerScorecard:
    return BrokerScorecard(
        broker_id=broker_id,
        fill_rate=fill_rate,
        avg_slippage_bps=avg_slippage_bps,
        avg_cost_bps=avg_cost_bps,
    )


def _make_service(
    routing_repo: AsyncMock | None = None,
    scorecard_service: AsyncMock | None = None,
) -> BestExecutionService:
    return BestExecutionService(
        routing_repo=routing_repo or AsyncMock(),
        scorecard_service=scorecard_service or AsyncMock(),
    )


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    async def test_report_with_decisions_and_scorecards(self):
        routing_repo = AsyncMock()
        scorecard_service = AsyncMock()

        d1 = _make_routing_decision(broker_id="broker-1", quantity=Decimal("200"), score=Decimal("0.90"))
        d2 = _make_routing_decision(broker_id="broker-2", quantity=Decimal("300"), score=Decimal("0.80"))
        d3 = _make_routing_decision(broker_id="broker-1", quantity=Decimal("100"), score=Decimal("0.85"))
        routing_repo.get_decisions_in_range.return_value = [d1, d2, d3]

        sc1 = _make_scorecard(broker_id="broker-1", avg_slippage_bps=Decimal("1.5"), avg_cost_bps=Decimal("3.0"))
        sc2 = _make_scorecard(broker_id="broker-2", avg_slippage_bps=Decimal("2.0"), avg_cost_bps=Decimal("4.0"))
        scorecard_service.get_all_scorecards.return_value = [sc1, sc2]

        svc = _make_service(routing_repo=routing_repo, scorecard_service=scorecard_service)

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)

        report = await svc.generate_report("alpha", start, end)

        assert report.fund_slug == "alpha"
        assert report.total_orders == 3
        assert len(report.broker_breakdown) == 2
        assert report.period_start == start
        assert report.period_end == end

    async def test_report_empty_decisions(self):
        routing_repo = AsyncMock()
        scorecard_service = AsyncMock()

        routing_repo.get_decisions_in_range.return_value = []
        scorecard_service.get_all_scorecards.return_value = []

        svc = _make_service(routing_repo=routing_repo, scorecard_service=scorecard_service)

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)

        report = await svc.generate_report("alpha", start, end)

        assert report.total_orders == 0
        assert report.broker_breakdown == []

    async def test_report_decisions_without_matching_scorecard(self):
        routing_repo = AsyncMock()
        scorecard_service = AsyncMock()

        d1 = _make_routing_decision(broker_id="broker-1", score=None)
        routing_repo.get_decisions_in_range.return_value = [d1]
        scorecard_service.get_all_scorecards.return_value = []

        svc = _make_service(routing_repo=routing_repo, scorecard_service=scorecard_service)

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)

        report = await svc.generate_report("alpha", start, end)

        assert report.total_orders == 1
        assert len(report.broker_breakdown) == 1


# ---------------------------------------------------------------------------
# get_order_execution_detail
# ---------------------------------------------------------------------------


class TestGetOrderExecutionDetail:
    async def test_detail_for_order(self):
        routing_repo = AsyncMock()
        d1 = _make_routing_decision(
            broker_id="broker-1",
            score=Decimal("0.90"),
            decision_reason="best_score",
        )
        d2 = _make_routing_decision(
            broker_id="broker-2",
            score=None,
            decision_reason="fallback",
        )
        routing_repo.get_decisions_for_order.return_value = [d1, d2]

        svc = _make_service(routing_repo=routing_repo)
        order_id = uuid4()

        result = await svc.get_order_execution_detail(order_id, "alpha")

        assert result["order_id"] == str(order_id)
        assert len(result["routing_decisions"]) == 2
        assert result["routing_decisions"][0]["broker_id"] == "broker-1"
        assert result["routing_decisions"][0]["score"] == "0.90"
        assert result["routing_decisions"][1]["score"] is None

    async def test_detail_empty(self):
        routing_repo = AsyncMock()
        routing_repo.get_decisions_for_order.return_value = []

        svc = _make_service(routing_repo=routing_repo)
        order_id = uuid4()

        result = await svc.get_order_execution_detail(order_id, "alpha")

        assert result["order_id"] == str(order_id)
        assert result["routing_decisions"] == []
