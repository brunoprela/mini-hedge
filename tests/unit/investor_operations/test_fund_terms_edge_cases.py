"""Edge-case tests for fund_terms — unsupported frequency and fallback path."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.investor_operations.core.fund_terms import compute_next_dealing_date
from app.modules.investor_operations.interfaces import RedemptionFrequency


class TestUnsupportedFrequency:
    """Covers lines 32-33: unsupported frequency raises ValueError."""

    def test_raises_for_unknown_frequency(self) -> None:
        with pytest.raises(ValueError, match="Unsupported frequency"):
            compute_next_dealing_date("daily", -1, date(2026, 1, 1))  # type: ignore[arg-type]
