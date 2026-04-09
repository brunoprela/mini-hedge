"""Escalation policies and SLA tracking for reconciliation breaks."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.modules.eod.interfaces.reconciliation import AgingBucket, AgingSummary, SLAStatus

if TYPE_CHECKING:
    from app.modules.eod.models import ReconciliationBreakRecord

ZERO = Decimal(0)


class EscalationPolicy:
    """Defines SLA and escalation rules for breaks."""

    def __init__(
        self,
        *,
        warn_after_hours: int = 4,
        escalate_after_hours: int = 24,
        critical_escalate_hours: int = 2,
        notify_emails: list[str] | None = None,
    ) -> None:
        self._warn_after_hours = warn_after_hours
        self._escalate_after_hours = escalate_after_hours
        self._critical_escalate_hours = critical_escalate_hours
        self._notify_emails = notify_emails or []

    def check_sla(self, break_record: ReconciliationBreakRecord) -> SLAStatus:
        """Return SLA status: within_sla, warning, or breached."""
        age_hours = self._age_hours(break_record)

        # Material breaks use the critical threshold
        if break_record.is_material:
            if age_hours >= self._critical_escalate_hours:
                return SLAStatus.BREACHED
            if age_hours >= self._critical_escalate_hours / 2:
                return SLAStatus.WARNING
            return SLAStatus.WITHIN_SLA

        if age_hours >= self._escalate_after_hours:
            return SLAStatus.BREACHED
        if age_hours >= self._warn_after_hours:
            return SLAStatus.WARNING
        return SLAStatus.WITHIN_SLA

    def get_aging_summary(self, breaks: list[ReconciliationBreakRecord]) -> AgingSummary:
        """Bucket breaks by age: <1h, 1-4h, 4-24h, >24h."""
        buckets_config: list[tuple[str, float, float]] = [
            ("<1h", 0, 1),
            ("1-4h", 1, 4),
            ("4-24h", 4, 24),
            (">24h", 24, float("inf")),
        ]

        bucket_counts: dict[str, int] = {label: 0 for label, _, _ in buckets_config}
        bucket_diffs: dict[str, Decimal] = {label: ZERO for label, _, _ in buckets_config}

        oldest_hours = 0.0
        sla_breached = 0

        for brk in breaks:
            age = self._age_hours(brk)
            if age > oldest_hours:
                oldest_hours = age

            if self.check_sla(brk) == SLAStatus.BREACHED:
                sla_breached += 1

            for label, lo, hi in buckets_config:
                if lo <= age < hi:
                    bucket_counts[label] += 1
                    bucket_diffs[label] += abs(brk.difference)
                    break

        aging_buckets = [
            AgingBucket(
                label=label,
                count=bucket_counts[label],
                total_difference=bucket_diffs[label],
            )
            for label, _, _ in buckets_config
        ]

        return AgingSummary(
            buckets=aging_buckets,
            oldest_break_hours=round(oldest_hours, 2),
            sla_breached_count=sla_breached,
        )

    @staticmethod
    def _age_hours(break_record: ReconciliationBreakRecord) -> float:
        """Return the age of a break in hours."""
        created = break_record.created_at.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - created
        return delta.total_seconds() / 3600
