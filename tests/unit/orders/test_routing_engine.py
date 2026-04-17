"""Unit tests for RoutingEngine — smart order routing with scorecards."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.orders.core.routing_engine import RoutingEngine


def _make_scorecard(
    fill_rate: Decimal = Decimal("0.95"),
    avg_slippage_bps: Decimal = Decimal("3"),
    avg_fill_time_ms: float = 50.0,
    avg_cost_bps: Decimal = Decimal("5"),
) -> MagicMock:
    s = MagicMock()
    s.fill_rate = fill_rate
    s.avg_slippage_bps = avg_slippage_bps
    s.avg_fill_time_ms = avg_fill_time_ms
    s.avg_cost_bps = avg_cost_bps
    return s


def _make_rule(
    preferred_broker_id: str = "broker-a",
    min_size: Decimal | None = None,
    max_size: Decimal | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = "rule-1"
    r.preferred_broker_id = preferred_broker_id
    r.min_size = min_size
    r.max_size = max_size
    return r


def _make_engine(
    broker_ids: list[str] | None = None,
    scorecard: MagicMock | None = None,
    rules: list | None = None,
    split_threshold: int = 50_000,
) -> RoutingEngine:
    broker_ids = broker_ids if broker_ids is not None else ["sim"]
    registry = MagicMock()
    registry.list_broker_ids.return_value = broker_ids

    scorecard_service = AsyncMock()
    scorecard_service.get_scorecard = AsyncMock(return_value=scorecard)

    routing_repo = AsyncMock()
    routing_repo.get_rules_for_fund = AsyncMock(return_value=rules or [])
    routing_repo.insert_decision = AsyncMock()

    return RoutingEngine(
        broker_registry=registry,
        scorecard_service=scorecard_service,
        routing_repo=routing_repo,
        split_threshold=split_threshold,
    )


class TestSingleBrokerMode:
    @pytest.mark.asyncio
    async def test_single_broker_passthrough(self) -> None:
        engine = _make_engine(["sim"])

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert len(slices) == 1
        assert slices[0].broker_id == "sim"
        assert slices[0].quantity == Decimal("100")
        assert slices[0].reason == "single broker mode"

    @pytest.mark.asyncio
    async def test_no_brokers_uses_default(self) -> None:
        engine = _make_engine([])

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert slices[0].broker_id == "default"


class TestRuleBasedRouting:
    @pytest.mark.asyncio
    async def test_matching_rule_routes_to_preferred(self) -> None:
        rule = _make_rule("broker-b")
        engine = _make_engine(["broker-a", "broker-b"], rules=[rule])

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert len(slices) == 1
        assert slices[0].broker_id == "broker-b"
        assert "routing rule" in slices[0].reason

    @pytest.mark.asyncio
    async def test_rule_min_size_filters(self) -> None:
        rule = _make_rule("broker-b", min_size=Decimal("1000"))
        engine = _make_engine(["broker-a", "broker-b"], rules=[rule])

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        # Order too small for rule — falls through to scoring
        assert slices[0].reason != "routing rule rule-1"

    @pytest.mark.asyncio
    async def test_rule_max_size_filters(self) -> None:
        rule = _make_rule("broker-b", max_size=Decimal("50"))
        engine = _make_engine(["broker-a", "broker-b"], rules=[rule])

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert slices[0].reason != "routing rule rule-1"

    @pytest.mark.asyncio
    async def test_rule_for_unregistered_broker_skipped(self) -> None:
        rule = _make_rule("broker-c")  # not registered
        engine = _make_engine(["broker-a", "broker-b"], rules=[rule])

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        # Falls through to scoring
        assert slices[0].broker_id in ("broker-a", "broker-b")


class TestScorecardRouting:
    @pytest.mark.asyncio
    async def test_best_scorecard_wins(self) -> None:
        good_card = _make_scorecard(
            fill_rate=Decimal("0.99"),
            avg_slippage_bps=Decimal("1"),
            avg_fill_time_ms=10.0,
            avg_cost_bps=Decimal("2"),
        )
        engine = _make_engine(["broker-a", "broker-b"], scorecard=good_card)

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert len(slices) == 1
        assert slices[0].score is not None
        assert slices[0].reason == "best scorecard"

    @pytest.mark.asyncio
    async def test_no_scorecard_gets_neutral_score(self) -> None:
        engine = _make_engine(["broker-a", "broker-b"], scorecard=None)

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert len(slices) == 1
        assert slices[0].score == Decimal("0.500000")


class TestOrderSplitting:
    @pytest.mark.asyncio
    async def test_large_order_splits_across_brokers(self) -> None:
        card = _make_scorecard()
        engine = _make_engine(
            ["broker-a", "broker-b"],
            scorecard=card,
            split_threshold=1000,
        )

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("5000"), "market", "fund-a",
        )

        assert len(slices) == 2
        total = sum(s.quantity for s in slices)
        assert total == Decimal("5000")
        assert all("split" in s.reason for s in slices)

    @pytest.mark.asyncio
    async def test_below_threshold_no_split(self) -> None:
        card = _make_scorecard()
        engine = _make_engine(
            ["broker-a", "broker-b"],
            scorecard=card,
            split_threshold=50_000,
        )

        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert len(slices) == 1


class TestDecisionRecording:
    @pytest.mark.asyncio
    async def test_decision_persisted(self) -> None:
        engine = _make_engine(["sim"])

        await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        engine._routing_repo.insert_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_decision_save_failure_does_not_crash(self) -> None:
        engine = _make_engine(["sim"])
        engine._routing_repo.insert_decision = AsyncMock(side_effect=RuntimeError("db down"))

        # Should not raise
        slices = await engine.route_order(
            "o-1", "AAPL", "equity", "buy", Decimal("100"), "market", "fund-a",
        )

        assert len(slices) == 1
