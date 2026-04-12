"""Unit tests for BreakAutoResolver and auto-resolution rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.eod.core.auto_resolver import (
    BreakAutoResolver,
    CashTimingRule,
    DuplicateBreakRule,
    ImmaterialBreakRule,
    RoundingDifferenceRule,
    StaleBreakRule,
    default_rules,
)
from app.modules.eod.interfaces.reconciliation import BreakStatus, BreakType


def _make_break(
    *,
    status: str = "open",
    difference: Decimal = Decimal("10.00"),
    is_material: bool = True,
    break_type: str = "quantity_mismatch",
    instrument_id: str | None = "AAPL",
    age_hours: float = 0,
) -> MagicMock:
    b = MagicMock()
    b.id = str(uuid4())
    b.status = status
    b.difference = difference
    b.is_material = is_material
    b.break_type = break_type
    b.instrument_id = instrument_id
    b.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
    return b


class TestImmaterialBreakRule:
    def test_matches_non_material_open(self) -> None:
        rule = ImmaterialBreakRule()
        brk = _make_break(is_material=False, status="open")
        assert rule.matches(brk) is True

    def test_skips_material_break(self) -> None:
        rule = ImmaterialBreakRule()
        brk = _make_break(is_material=True, status="open")
        assert rule.matches(brk) is False

    def test_skips_non_open(self) -> None:
        rule = ImmaterialBreakRule()
        brk = _make_break(is_material=False, status="resolved")
        assert rule.matches(brk) is False

    def test_resolution_note(self) -> None:
        rule = ImmaterialBreakRule()
        brk = _make_break(is_material=False)
        assert "materiality" in rule.resolution_note(brk)

    def test_target_status_is_resolved(self) -> None:
        rule = ImmaterialBreakRule()
        assert rule.target_status() == BreakStatus.RESOLVED


class TestRoundingDifferenceRule:
    def test_matches_tiny_difference(self) -> None:
        rule = RoundingDifferenceRule()
        brk = _make_break(difference=Decimal("0.003"))
        assert rule.matches(brk) is True

    def test_matches_exact_threshold(self) -> None:
        rule = RoundingDifferenceRule()
        brk = _make_break(difference=Decimal("0.005"))
        assert rule.matches(brk) is True

    def test_skips_above_threshold(self) -> None:
        rule = RoundingDifferenceRule()
        brk = _make_break(difference=Decimal("0.006"))
        assert rule.matches(brk) is False

    def test_matches_negative_tiny_difference(self) -> None:
        rule = RoundingDifferenceRule()
        brk = _make_break(difference=Decimal("-0.004"))
        assert rule.matches(brk) is True

    def test_skips_non_open(self) -> None:
        rule = RoundingDifferenceRule()
        brk = _make_break(difference=Decimal("0.001"), status="escalated")
        assert rule.matches(brk) is False


class TestStaleBreakRule:
    def test_matches_old_break(self) -> None:
        rule = StaleBreakRule(max_age_days=5)
        brk = _make_break(age_hours=24 * 6)  # 6 days old
        assert rule.matches(brk) is True

    def test_skips_recent_break(self) -> None:
        rule = StaleBreakRule(max_age_days=5)
        brk = _make_break(age_hours=24 * 3)  # 3 days old
        assert rule.matches(brk) is False

    def test_skips_non_open(self) -> None:
        rule = StaleBreakRule(max_age_days=5)
        brk = _make_break(age_hours=24 * 10, status="resolved")
        assert rule.matches(brk) is False

    def test_target_status_is_escalated(self) -> None:
        rule = StaleBreakRule()
        assert rule.target_status() == BreakStatus.ESCALATED


class TestCashTimingRule:
    def test_matches_small_cash_mismatch(self) -> None:
        rule = CashTimingRule()
        brk = _make_break(break_type=BreakType.CASH_MISMATCH.value, difference=Decimal("50"))
        assert rule.matches(brk) is True

    def test_skips_large_cash_mismatch(self) -> None:
        rule = CashTimingRule()
        brk = _make_break(break_type=BreakType.CASH_MISMATCH.value, difference=Decimal("150"))
        assert rule.matches(brk) is False

    def test_skips_non_cash_break(self) -> None:
        rule = CashTimingRule()
        brk = _make_break(break_type="quantity_mismatch", difference=Decimal("50"))
        assert rule.matches(brk) is False


class TestDuplicateBreakRule:
    def test_matches_previously_resolved_key(self) -> None:
        rule = DuplicateBreakRule()
        resolved = _make_break(instrument_id="AAPL", break_type="quantity_mismatch")
        rule.set_resolved_context([resolved])

        brk = _make_break(instrument_id="AAPL", break_type="quantity_mismatch")
        assert rule.matches(brk) is True

    def test_skips_unknown_key(self) -> None:
        rule = DuplicateBreakRule()
        rule.set_resolved_context([])
        brk = _make_break(instrument_id="MSFT", break_type="quantity_mismatch")
        assert rule.matches(brk) is False

    def test_skips_non_open(self) -> None:
        rule = DuplicateBreakRule()
        resolved = _make_break(instrument_id="AAPL", break_type="quantity_mismatch")
        rule.set_resolved_context([resolved])
        brk = _make_break(instrument_id="AAPL", break_type="quantity_mismatch", status="resolved")
        assert rule.matches(brk) is False


class TestBreakAutoResolver:
    @pytest.mark.asyncio
    async def test_resolves_immaterial_breaks(self) -> None:
        brk = _make_break(is_material=False)
        break_repo = AsyncMock()
        break_repo.list_open = AsyncMock(return_value=[brk])
        break_repo.list_recently_resolved = AsyncMock(return_value=[])
        break_repo.update_status = AsyncMock()

        resolver = BreakAutoResolver(rules=default_rules(), break_repo=break_repo)
        result = await resolver.process_breaks("port-1", datetime.now(UTC).date())

        assert result.auto_resolved == 1
        assert result.auto_escalated == 0
        break_repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_escalates_stale_breaks(self) -> None:
        brk = _make_break(is_material=True, age_hours=24 * 7)
        break_repo = AsyncMock()
        break_repo.list_open = AsyncMock(return_value=[brk])
        break_repo.list_recently_resolved = AsyncMock(return_value=[])
        break_repo.update_status = AsyncMock()

        resolver = BreakAutoResolver(rules=default_rules(), break_repo=break_repo)
        result = await resolver.process_breaks("port-1", datetime.now(UTC).date())

        assert result.auto_escalated == 1
        assert result.auto_resolved == 0
        # Verify status was set to escalated
        call_kwargs = break_repo.update_status.call_args
        assert call_kwargs.kwargs["status"] == "escalated"

    @pytest.mark.asyncio
    async def test_first_matching_rule_wins(self) -> None:
        # A rounding difference that is also immaterial — rounding rule comes first
        brk = _make_break(
            difference=Decimal("0.003"),
            is_material=False,
        )
        break_repo = AsyncMock()
        break_repo.list_open = AsyncMock(return_value=[brk])
        break_repo.list_recently_resolved = AsyncMock(return_value=[])
        break_repo.update_status = AsyncMock()

        resolver = BreakAutoResolver(rules=default_rules(), break_repo=break_repo)
        result = await resolver.process_breaks("port-1", datetime.now(UTC).date())

        assert result.auto_resolved == 1
        assert "rounding_difference" in result.rules_applied

    @pytest.mark.asyncio
    async def test_no_open_breaks(self) -> None:
        break_repo = AsyncMock()
        break_repo.list_open = AsyncMock(return_value=[])
        break_repo.list_recently_resolved = AsyncMock(return_value=[])

        resolver = BreakAutoResolver(rules=default_rules(), break_repo=break_repo)
        result = await resolver.process_breaks("port-1", datetime.now(UTC).date())

        assert result.auto_resolved == 0
        assert result.auto_escalated == 0
        assert result.rules_applied == []

    @pytest.mark.asyncio
    async def test_multiple_breaks_different_rules(self) -> None:
        rounding_brk = _make_break(difference=Decimal("0.002"), is_material=True)
        immaterial_brk = _make_break(difference=Decimal("500"), is_material=False)
        stale_brk = _make_break(difference=Decimal("1000"), is_material=True, age_hours=24 * 10)

        break_repo = AsyncMock()
        break_repo.list_open = AsyncMock(return_value=[rounding_brk, immaterial_brk, stale_brk])
        break_repo.list_recently_resolved = AsyncMock(return_value=[])
        break_repo.update_status = AsyncMock()

        resolver = BreakAutoResolver(rules=default_rules(), break_repo=break_repo)
        result = await resolver.process_breaks("port-1", datetime.now(UTC).date())

        assert result.auto_resolved == 2  # rounding + immaterial
        assert result.auto_escalated == 1  # stale
        assert break_repo.update_status.call_count == 3


class TestDefaultRules:
    def test_returns_all_five_rules(self) -> None:
        rules = default_rules()
        assert len(rules) == 5
        names = [r.name for r in rules]
        assert "rounding_difference" in names
        assert "immaterial_break" in names
        assert "cash_timing" in names
        assert "duplicate_break" in names
        assert "stale_break" in names
