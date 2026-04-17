"""Unit tests for fee accounting batch trigger and summary routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.fee_accounting.routes.fee import (
    AccrualTriggerRequest,
    CrystallizationTriggerRequest,
    FeeSummaryResponse,
)


class TestAccrualTriggerRequestModel:
    def test_valid_request(self) -> None:
        req = AccrualTriggerRequest(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            nav=Decimal("100000000"),
            business_date=date(2026, 4, 10),
        )
        assert req.share_class == "default"
        assert req.nav == Decimal("100000000")

    def test_custom_share_class(self) -> None:
        req = AccrualTriggerRequest(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            nav=Decimal("100000000"),
            business_date=date(2026, 4, 10),
            share_class="founders",
        )
        assert req.share_class == "founders"

    def test_allows_missing_portfolio_id_for_fund_wide_accrual(self) -> None:
        """When portfolio_id is omitted, the request is valid — the route
        iterates over all fund portfolios."""
        req = AccrualTriggerRequest(
            nav=Decimal("100000000"),
            business_date=date(2026, 4, 10),
        )
        assert req.portfolio_id is None

    def test_allows_missing_nav_for_fund_wide_accrual(self) -> None:
        """When portfolio_id is omitted, nav is optional too — each portfolio
        computes its own nav from the current snapshot."""
        req = AccrualTriggerRequest(
            business_date=date(2026, 4, 10),
        )
        assert req.nav is None


class TestCrystallizationTriggerRequestModel:
    def test_valid_request(self) -> None:
        req = CrystallizationTriggerRequest(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            business_date=date(2026, 3, 31),
        )
        assert req.share_class == "default"

    def test_missing_business_date_raises(self) -> None:
        with pytest.raises(ValidationError):
            CrystallizationTriggerRequest(
                portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            )


class TestFeeSummaryResponseModel:
    def test_valid_response(self) -> None:
        resp = FeeSummaryResponse(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            totals={"management": Decimal("5000"), "performance": Decimal("12000")},
        )
        assert resp.totals["management"] == Decimal("5000")

    def test_empty_totals(self) -> None:
        resp = FeeSummaryResponse(
            portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
            totals={},
        )
        assert resp.totals == {}
