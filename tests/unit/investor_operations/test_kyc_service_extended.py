"""Extended tests for InvestorKYCService — covers update path, get/list, upsert fund terms."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.investor_operations.interfaces import (
    FundTermsSummary,
    RedemptionFrequency,
)
from app.modules.investor_operations.models.fund_terms import FundTermsRecord
from app.modules.investor_operations.services.kyc import InvestorKYCService


def _make_service(
    *,
    kyc_repo: AsyncMock | None = None,
    terms_repo: AsyncMock | None = None,
    kyc_adapter: AsyncMock | None = None,
    event_bus: AsyncMock | None = None,
) -> InvestorKYCService:
    return InvestorKYCService(
        kyc_repo=kyc_repo or AsyncMock(),
        fund_terms_repo=terms_repo or AsyncMock(),
        kyc_adapter=kyc_adapter or AsyncMock(),
        event_bus=event_bus,
    )


def _screening_result(**overrides) -> MagicMock:
    r = MagicMock()
    r.kyc_status = "approved"
    r.aml_status = "cleared"
    r.sanctions_clear = True
    r.pep_flag = False
    r.source_of_funds_verified = True
    r.screening_provider = "test-provider"
    r.notes = ""
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _kyc_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.investor_id = str(uuid4())
    r.kyc_status = "approved"
    r.aml_status = "cleared"
    r.sanctions_clear = True
    r.pep_flag = False
    r.source_of_funds_verified = True
    r.accredited_investor = True
    r.last_screened_at = datetime.now(UTC)
    r.screening_expires_at = None
    r.screening_provider = "test-provider"
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _terms_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.share_class = "default"
    r.lock_up_months = 12
    r.notice_period_days = 45
    r.redemption_frequency = "quarterly"
    r.gate_pct = Decimal("0.25")
    r.minimum_subscription = Decimal("1000000")
    r.minimum_redemption = Decimal("100000")
    r.dealing_day = -1
    r.payment_days = 30
    r.is_active = True
    r.created_at = datetime.now(UTC)
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


class TestScreenInvestorUpdatePath:
    """Covers lines 69-78: updating an existing KYC record."""

    @pytest.mark.asyncio
    async def test_updates_existing_record(self) -> None:
        existing = _kyc_record()
        kyc_repo = AsyncMock()
        kyc_repo.get_by_investor = AsyncMock(return_value=existing)
        kyc_repo.upsert = AsyncMock()

        adapter = AsyncMock()
        adapter.screen_investor = AsyncMock(
            return_value=_screening_result(kyc_status="pending", aml_status="flagged")
        )

        service = _make_service(kyc_repo=kyc_repo, kyc_adapter=adapter)
        result = await service.screen_investor(
            investor_id=existing.investor_id, name="Jane Doe"
        )

        assert result.kyc_status == "pending"
        assert result.aml_status == "flagged"
        # The existing record should have been updated and upserted
        assert existing.kyc_status == "pending"
        assert existing.aml_status == "flagged"
        kyc_repo.upsert.assert_called_once()


class TestGetInvestorKYC:
    """Covers lines 131-134: returning InvestorKYCInfo from a record."""

    @pytest.mark.asyncio
    async def test_returns_info_when_found(self) -> None:
        inv_id = str(uuid4())
        record = _kyc_record(investor_id=inv_id)
        kyc_repo = AsyncMock()
        kyc_repo.get_by_investor = AsyncMock(return_value=record)

        service = _make_service(kyc_repo=kyc_repo)
        result = await service.get_investor_kyc(inv_id)

        assert result is not None
        assert result.kyc_status == "approved"
        assert result.accredited_investor is True

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        kyc_repo = AsyncMock()
        kyc_repo.get_by_investor = AsyncMock(return_value=None)

        service = _make_service(kyc_repo=kyc_repo)
        result = await service.get_investor_kyc(str(uuid4()))

        assert result is None


class TestGetFundTerms:
    """Covers lines 153-156: returning FundTermsSummary from a record."""

    @pytest.mark.asyncio
    async def test_returns_summary_when_found(self) -> None:
        record = _terms_record()
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=record)

        service = _make_service(terms_repo=terms_repo)
        result = await service.get_fund_terms("default")

        assert result is not None
        assert isinstance(result, FundTermsSummary)
        assert result.share_class == "default"
        assert result.redemption_frequency == RedemptionFrequency.QUARTERLY

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=None)

        service = _make_service(terms_repo=terms_repo)
        result = await service.get_fund_terms("nonexistent")

        assert result is None


class TestListFundTerms:
    """Covers lines 161-162."""

    @pytest.mark.asyncio
    async def test_returns_list_of_summaries(self) -> None:
        records = [_terms_record(share_class="A"), _terms_record(share_class="B")]
        terms_repo = AsyncMock()
        terms_repo.get_all_active = AsyncMock(return_value=records)

        service = _make_service(terms_repo=terms_repo)
        result = await service.list_fund_terms()

        assert len(result) == 2
        assert result[0].share_class == "A"
        assert result[1].share_class == "B"

    @pytest.mark.asyncio
    async def test_returns_empty_list(self) -> None:
        terms_repo = AsyncMock()
        terms_repo.get_all_active = AsyncMock(return_value=[])

        service = _make_service(terms_repo=terms_repo)
        result = await service.list_fund_terms()

        assert result == []


class TestUpsertFundTerms:
    """Covers lines 178-203: both update and create paths."""

    @pytest.mark.asyncio
    async def test_creates_new_terms(self) -> None:
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=None)
        terms_repo.upsert = AsyncMock()

        # FundTermsRecord has server_default fields (id, is_active) that are None
        # in unit tests.  Patch the constructor to set them.
        fake_id = str(uuid4())
        original_init = FundTermsRecord.__init__  # type: ignore[misc]

        def _patched_init(self, **kwargs):
            original_init(self, **kwargs)
            if self.id is None:
                self.id = fake_id
            if self.is_active is None:
                self.is_active = True

        with patch.object(FundTermsRecord, "__init__", _patched_init):
            service = _make_service(terms_repo=terms_repo)
            result = await service.upsert_fund_terms(
                share_class="class-A",
                lock_up_months=6,
                notice_period_days=30,
                redemption_frequency="monthly",
                gate_pct=Decimal("0.15"),
                minimum_subscription=Decimal("500000"),
                minimum_redemption=Decimal("50000"),
                dealing_day=15,
                payment_days=14,
            )

        assert isinstance(result, FundTermsSummary)
        assert result.share_class == "class-A"
        assert result.lock_up_months == 6
        assert result.redemption_frequency == RedemptionFrequency.MONTHLY
        terms_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_terms(self) -> None:
        existing = _terms_record(share_class="default")
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=existing)
        terms_repo.upsert = AsyncMock()

        service = _make_service(terms_repo=terms_repo)
        result = await service.upsert_fund_terms(
            share_class="default",
            lock_up_months=24,
            notice_period_days=60,
        )

        assert isinstance(result, FundTermsSummary)
        # The existing record should have been mutated
        assert existing.lock_up_months == 24
        assert existing.notice_period_days == 60
        terms_repo.upsert.assert_called_once()
