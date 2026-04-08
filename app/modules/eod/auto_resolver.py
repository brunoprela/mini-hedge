"""Auto-resolution rules engine for reconciliation breaks.

Applies rule-based auto-resolution and auto-escalation to open breaks,
reducing manual intervention for immaterial or well-understood differences.
"""

from __future__ import annotations

import abc
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.eod.interface import AutoResolutionResult, BreakStatus, BreakType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.eod.models import ReconciliationBreakRecord
    from app.modules.eod.repository import ReconciliationBreakRepository

logger = structlog.get_logger()


class AutoResolutionRule(abc.ABC):
    """A rule that can auto-resolve a break."""

    name: str
    description: str

    @abc.abstractmethod
    def matches(self, break_record: ReconciliationBreakRecord) -> bool:
        """Return True if this rule applies to the given break."""

    @abc.abstractmethod
    def resolution_note(self, break_record: ReconciliationBreakRecord) -> str:
        """Return the note to attach when auto-resolving."""

    def target_status(self) -> BreakStatus:
        """Status to set when rule matches. Override for escalation rules."""
        return BreakStatus.RESOLVED


class ImmaterialBreakRule(AutoResolutionRule):
    """Auto-resolve non-material breaks (is_material=False)."""

    name = "immaterial_break"
    description = "Auto-resolve breaks below the materiality threshold"

    def matches(self, break_record: ReconciliationBreakRecord) -> bool:
        return (
            not break_record.is_material
            and break_record.status == BreakStatus.OPEN.value
        )

    def resolution_note(self, break_record: ReconciliationBreakRecord) -> str:
        return "Auto-resolved: below materiality threshold"


class RoundingDifferenceRule(AutoResolutionRule):
    """Auto-resolve where abs(difference) <= 0.005 (half-penny rounding)."""

    name = "rounding_difference"
    description = "Auto-resolve half-penny rounding differences"

    _threshold = Decimal("0.005")

    def matches(self, break_record: ReconciliationBreakRecord) -> bool:
        return (
            abs(break_record.difference) <= self._threshold
            and break_record.status == BreakStatus.OPEN.value
        )

    def resolution_note(self, break_record: ReconciliationBreakRecord) -> str:
        return f"Auto-resolved: rounding difference ({break_record.difference})"


class StaleBreakRule(AutoResolutionRule):
    """Auto-escalate breaks older than N days that are still open."""

    name = "stale_break"
    description = "Auto-escalate breaks that remain open beyond the SLA window"

    def __init__(self, *, max_age_days: int = 5) -> None:
        self._max_age_days = max_age_days

    def matches(self, break_record: ReconciliationBreakRecord) -> bool:
        if break_record.status != BreakStatus.OPEN.value:
            return False
        age = datetime.now(UTC) - break_record.created_at.replace(tzinfo=UTC)
        return age > timedelta(days=self._max_age_days)

    def resolution_note(self, break_record: ReconciliationBreakRecord) -> str:
        return f"Auto-escalated: open for more than {self._max_age_days} days"

    def target_status(self) -> BreakStatus:
        return BreakStatus.ESCALATED


class DuplicateBreakRule(AutoResolutionRule):
    """Auto-resolve if the same instrument+break_type was already resolved recently."""

    name = "duplicate_break"
    description = "Auto-resolve recurring immaterial breaks seen in the last 3 days"

    def __init__(self) -> None:
        self._resolved_keys: set[tuple[str | None, str]] = set()

    def set_resolved_context(
        self, recently_resolved: list[ReconciliationBreakRecord]
    ) -> None:
        """Pre-load the set of (instrument_id, break_type) resolved in the last 3 days."""
        self._resolved_keys = {
            (r.instrument_id, r.break_type) for r in recently_resolved
        }

    def matches(self, break_record: ReconciliationBreakRecord) -> bool:
        if break_record.status != BreakStatus.OPEN.value:
            return False
        key = (break_record.instrument_id, break_record.break_type)
        return key in self._resolved_keys

    def resolution_note(self, break_record: ReconciliationBreakRecord) -> str:
        return "Auto-resolved: recurring immaterial break"


class CashTimingRule(AutoResolutionRule):
    """Auto-resolve cash mismatches under $100 (likely settlement timing)."""

    name = "cash_timing"
    description = "Auto-resolve small cash mismatches likely caused by settlement timing"

    _threshold = Decimal("100")

    def matches(self, break_record: ReconciliationBreakRecord) -> bool:
        return (
            break_record.break_type == BreakType.CASH_MISMATCH.value
            and abs(break_record.difference) < self._threshold
            and break_record.status == BreakStatus.OPEN.value
        )

    def resolution_note(self, break_record: ReconciliationBreakRecord) -> str:
        return "Auto-resolved: likely settlement timing difference"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BreakAutoResolver:
    """Apply a list of auto-resolution rules to open breaks."""

    def __init__(
        self,
        rules: list[AutoResolutionRule],
        break_repo: ReconciliationBreakRepository,
    ) -> None:
        self._rules = rules
        self._break_repo = break_repo

    async def process_breaks(
        self,
        portfolio_id: str,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> AutoResolutionResult:
        """Apply all rules to open breaks, auto-resolve or escalate matches."""
        open_breaks = await self._break_repo.list_open(
            portfolio_id, session=session
        )

        # Pre-load context for the DuplicateBreakRule
        for rule in self._rules:
            if isinstance(rule, DuplicateBreakRule):
                recently_resolved = await self._break_repo.list_recently_resolved(
                    portfolio_id,
                    since=business_date - timedelta(days=3),
                    session=session,
                )
                rule.set_resolved_context(recently_resolved)

        auto_resolved = 0
        auto_escalated = 0
        rules_applied: list[str] = []

        for brk in open_breaks:
            for rule in self._rules:
                if rule.matches(brk):
                    target = rule.target_status()
                    resolved_at = (
                        datetime.now(UTC)
                        if target == BreakStatus.RESOLVED
                        else None
                    )
                    await self._break_repo.update_status(
                        brk.id,
                        status=target.value,
                        resolution_note=rule.resolution_note(brk),
                        resolved_at=resolved_at,
                        session=session,
                    )
                    if target == BreakStatus.RESOLVED:
                        auto_resolved += 1
                    elif target == BreakStatus.ESCALATED:
                        auto_escalated += 1
                    if rule.name not in rules_applied:
                        rules_applied.append(rule.name)
                    break  # first matching rule wins

        logger.info(
            "auto_resolution_complete",
            portfolio_id=portfolio_id,
            business_date=str(business_date),
            auto_resolved=auto_resolved,
            auto_escalated=auto_escalated,
            rules_applied=rules_applied,
        )

        return AutoResolutionResult(
            auto_resolved=auto_resolved,
            auto_escalated=auto_escalated,
            rules_applied=rules_applied,
        )


def default_rules() -> list[AutoResolutionRule]:
    """Return the standard set of auto-resolution rules."""
    return [
        RoundingDifferenceRule(),
        ImmaterialBreakRule(),
        CashTimingRule(),
        DuplicateBreakRule(),
        StaleBreakRule(),
    ]
