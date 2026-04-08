"""Unit tests for the redemption gate engine — pro-ration logic."""

from decimal import Decimal
from uuid import uuid4

from app.modules.investor_operations.gate_engine import check_gate


def _rid() -> str:
    return str(uuid4())


class TestGateEngine:
    def test_empty_requests(self) -> None:
        result = check_gate([], Decimal("10000000"), Decimal("0.25"))
        assert result.gate_triggered is False
        assert result.total_requested == 0
        assert result.total_approved == 0
        assert result.gate_capacity == Decimal("2500000")
        assert result.allocations == []

    def test_within_gate_capacity(self) -> None:
        r1, r2 = _rid(), _rid()
        result = check_gate(
            [(r1, Decimal("1000000")), (r2, Decimal("500000"))],
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )
        assert result.gate_triggered is False
        assert result.total_requested == Decimal("1500000")
        assert result.total_approved == Decimal("1500000")
        assert len(result.allocations) == 2
        assert result.allocations[0].approved_amount == Decimal("1000000")
        assert result.allocations[1].approved_amount == Decimal("500000")

    def test_exactly_at_gate_capacity(self) -> None:
        r1 = _rid()
        result = check_gate(
            [(r1, Decimal("2500000"))],
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )
        assert result.gate_triggered is False
        assert result.allocations[0].approved_amount == Decimal("2500000")

    def test_exceeds_gate_triggers_proration(self) -> None:
        r1, r2 = _rid(), _rid()
        result = check_gate(
            [(r1, Decimal("3000000")), (r2, Decimal("2000000"))],
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )
        assert result.gate_triggered is True
        assert result.total_requested == Decimal("5000000")
        assert result.total_approved == Decimal("2500000")
        assert result.gate_capacity == Decimal("2500000")

        # Pro-rated amounts should sum to gate capacity
        total_approved = sum(a.approved_amount for a in result.allocations)
        assert total_approved == Decimal("2500000")

    def test_proration_preserves_proportions(self) -> None:
        r1, r2 = _rid(), _rid()
        result = check_gate(
            [(r1, Decimal("6000000")), (r2, Decimal("4000000"))],
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )
        assert result.gate_triggered is True
        # r1 requested 60%, r2 40% — approved amounts should roughly follow
        a1 = result.allocations[0].approved_amount
        a2 = result.allocations[1].approved_amount
        assert a1 > a2
        assert a1 + a2 == Decimal("2500000")

    def test_single_request_exceeds_gate(self) -> None:
        r1 = _rid()
        result = check_gate(
            [(r1, Decimal("5000000"))],
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )
        assert result.gate_triggered is True
        assert result.allocations[0].approved_amount == Decimal("2500000")

    def test_many_small_requests(self) -> None:
        requests = [(_rid(), Decimal("1000000")) for _ in range(10)]
        result = check_gate(
            requests,
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )
        assert result.gate_triggered is True
        total_approved = sum(a.approved_amount for a in result.allocations)
        assert total_approved == Decimal("2500000")

    def test_different_gate_pct(self) -> None:
        r1 = _rid()
        result = check_gate(
            [(r1, Decimal("600000"))],
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.05"),
        )
        assert result.gate_triggered is True
        assert result.gate_capacity == Decimal("500000")
        assert result.allocations[0].approved_amount == Decimal("500000")
