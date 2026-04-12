"""Unit tests for EscalationPolicy — SLA checks and aging summaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.eod.core.escalation import EscalationPolicy
from app.modules.eod.interfaces.reconciliation import SLAStatus


def _make_break(
    *,
    is_material: bool = False,
    age_hours: float = 0,
    difference: Decimal = Decimal("100"),
) -> MagicMock:
    b = MagicMock()
    b.id = str(uuid4())
    b.is_material = is_material
    b.difference = difference
    b.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
    return b


class TestCheckSLA:
    def test_fresh_break_within_sla(self) -> None:
        policy = EscalationPolicy()
        brk = _make_break(age_hours=1)
        assert policy.check_sla(brk) == SLAStatus.WITHIN_SLA

    def test_warning_after_threshold(self) -> None:
        policy = EscalationPolicy(warn_after_hours=4)
        brk = _make_break(age_hours=5)
        assert policy.check_sla(brk) == SLAStatus.WARNING

    def test_breached_after_escalation_threshold(self) -> None:
        policy = EscalationPolicy(escalate_after_hours=24)
        brk = _make_break(age_hours=25)
        assert policy.check_sla(brk) == SLAStatus.BREACHED

    def test_material_break_uses_critical_threshold(self) -> None:
        policy = EscalationPolicy(critical_escalate_hours=2)
        brk = _make_break(is_material=True, age_hours=3)
        assert policy.check_sla(brk) == SLAStatus.BREACHED

    def test_material_break_warning_at_half_critical(self) -> None:
        policy = EscalationPolicy(critical_escalate_hours=4)
        brk = _make_break(is_material=True, age_hours=2.5)
        assert policy.check_sla(brk) == SLAStatus.WARNING

    def test_material_break_within_sla_when_fresh(self) -> None:
        policy = EscalationPolicy(critical_escalate_hours=4)
        brk = _make_break(is_material=True, age_hours=0.5)
        assert policy.check_sla(brk) == SLAStatus.WITHIN_SLA


class TestGetAgingSummary:
    def test_single_break_in_correct_bucket(self) -> None:
        policy = EscalationPolicy()
        brk = _make_break(age_hours=0.5, difference=Decimal("200"))
        summary = policy.get_aging_summary([brk])

        assert summary.buckets[0].label == "<1h"
        assert summary.buckets[0].count == 1
        assert summary.buckets[0].total_difference == Decimal("200")

    def test_multiple_breaks_across_buckets(self) -> None:
        policy = EscalationPolicy()
        breaks = [
            _make_break(age_hours=0.5, difference=Decimal("100")),
            _make_break(age_hours=2, difference=Decimal("200")),
            _make_break(age_hours=10, difference=Decimal("300")),
            _make_break(age_hours=30, difference=Decimal("400")),
        ]
        summary = policy.get_aging_summary(breaks)

        assert summary.buckets[0].count == 1  # <1h
        assert summary.buckets[1].count == 1  # 1-4h
        assert summary.buckets[2].count == 1  # 4-24h
        assert summary.buckets[3].count == 1  # >24h

    def test_oldest_break_hours(self) -> None:
        policy = EscalationPolicy()
        breaks = [
            _make_break(age_hours=2),
            _make_break(age_hours=48),
        ]
        summary = policy.get_aging_summary(breaks)
        assert summary.oldest_break_hours >= 47  # Allow tiny timing variance

    def test_sla_breached_count(self) -> None:
        policy = EscalationPolicy(escalate_after_hours=24)
        breaks = [
            _make_break(age_hours=1),
            _make_break(age_hours=25),
            _make_break(age_hours=50),
        ]
        summary = policy.get_aging_summary(breaks)
        assert summary.sla_breached_count == 2

    def test_empty_breaks(self) -> None:
        policy = EscalationPolicy()
        summary = policy.get_aging_summary([])
        assert summary.oldest_break_hours == 0
        assert summary.sla_breached_count == 0
        assert all(b.count == 0 for b in summary.buckets)

    def test_bucket_differences_accumulate(self) -> None:
        policy = EscalationPolicy()
        breaks = [
            _make_break(age_hours=0.3, difference=Decimal("100")),
            _make_break(age_hours=0.6, difference=Decimal("250")),
        ]
        summary = policy.get_aging_summary(breaks)
        assert summary.buckets[0].count == 2
        assert summary.buckets[0].total_difference == Decimal("350")
