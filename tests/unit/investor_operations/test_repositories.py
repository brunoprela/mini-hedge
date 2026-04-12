"""Unit tests for investor_operations repositories — verifies SQL construction with mocked sessions."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.investor_operations.models.fund_terms import FundTermsRecord
from app.modules.investor_operations.models.kyc import InvestorKYCRecord
from app.modules.investor_operations.models.redemption import RedemptionRequestRecord
from app.modules.investor_operations.models.subscription import SubscriptionRequestRecord
from app.modules.investor_operations.repositories.fund_terms import FundTermsRepository
from app.modules.investor_operations.repositories.kyc import InvestorKYCRepository
from app.modules.investor_operations.repositories.redemption import (
    RedemptionRequestRepository,
)
from app.modules.investor_operations.repositories.subscription import (
    SubscriptionRequestRepository,
)


def _mock_session() -> AsyncMock:
    """Create a mock session with execute/add/flush methods."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _mock_session_factory(session: AsyncMock | None = None) -> MagicMock:
    """Create a mock TenantSessionFactory that yields the given session."""
    s = session or _mock_session()
    sf = MagicMock()

    @asynccontextmanager
    async def _call():
        yield s

    sf.__call__ = _call
    sf.return_value = _call()
    return sf


# ---------------------------------------------------------------------------
#  FundTermsRepository
# ---------------------------------------------------------------------------


class TestFundTermsRepository:
    @pytest.mark.asyncio
    async def test_get_by_share_class(self) -> None:
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = MagicMock(spec=FundTermsRecord)
        session.execute = AsyncMock(return_value=result_mock)

        repo = FundTermsRepository(MagicMock())
        result = await repo.get_by_share_class("default", session=session)

        assert result is not None
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_active(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [MagicMock(spec=FundTermsRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = FundTermsRepository(MagicMock())
        result = await repo.get_all_active(session=session)

        assert len(result) == 1
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_transient_record(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=FundTermsRecord)

        # Simulate a transient record (not yet in session)
        inspected = MagicMock()
        inspected.transient = True

        repo = FundTermsRepository(MagicMock())
        with patch("app.modules.investor_operations.repositories.fund_terms.sa.inspect", return_value=inspected):
            await repo.upsert(record, session=session)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_persistent_record(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=FundTermsRecord)

        # Simulate a persistent record (already tracked)
        inspected = MagicMock()
        inspected.transient = False

        repo = FundTermsRepository(MagicMock())
        with patch("app.modules.investor_operations.repositories.fund_terms.sa.inspect", return_value=inspected):
            await repo.upsert(record, session=session)

        session.add.assert_not_called()
        session.flush.assert_called_once()


# ---------------------------------------------------------------------------
#  InvestorKYCRepository
# ---------------------------------------------------------------------------


class TestInvestorKYCRepository:
    @pytest.mark.asyncio
    async def test_get_by_investor(self) -> None:
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = MagicMock(spec=InvestorKYCRecord)
        session.execute = AsyncMock(return_value=result_mock)

        repo = InvestorKYCRepository(MagicMock())
        result = await repo.get_by_investor("inv-1", session=session)

        assert result is not None
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_transient(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=InvestorKYCRecord)

        inspected = MagicMock()
        inspected.transient = True

        repo = InvestorKYCRepository(MagicMock())
        with patch("app.modules.investor_operations.repositories.kyc.sa.inspect", return_value=inspected):
            await repo.upsert(record, session=session)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_persistent(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=InvestorKYCRecord)

        inspected = MagicMock()
        inspected.transient = False

        repo = InvestorKYCRepository(MagicMock())
        with patch("app.modules.investor_operations.repositories.kyc.sa.inspect", return_value=inspected):
            await repo.upsert(record, session=session)

        session.add.assert_not_called()
        session.flush.assert_called_once()


# ---------------------------------------------------------------------------
#  RedemptionRequestRepository
# ---------------------------------------------------------------------------


class TestRedemptionRequestRepository:
    @pytest.mark.asyncio
    async def test_save(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=RedemptionRequestRecord)

        repo = RedemptionRequestRepository(MagicMock())
        await repo.save(record, session=session)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = MagicMock(spec=RedemptionRequestRecord)
        session.execute = AsyncMock(return_value=result_mock)

        repo = RedemptionRequestRepository(MagicMock())
        result = await repo.get_by_id("req-1", session=session)

        assert result is not None

    @pytest.mark.asyncio
    async def test_list_by_state(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [MagicMock(spec=RedemptionRequestRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = RedemptionRequestRepository(MagicMock())
        result = await repo.list_by_state("pending_validation", session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_by_investor(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = RedemptionRequestRepository(MagicMock())
        result = await repo.list_by_investor("inv-1", session=session)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_by_dealing_date(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = RedemptionRequestRepository(MagicMock())
        result = await repo.list_by_dealing_date(date(2026, 6, 30), session=session)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_pending_for_gate(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = RedemptionRequestRepository(MagicMock())
        result = await repo.list_pending_for_gate(session=session)

        assert result == []

    @pytest.mark.asyncio
    async def test_update_state(self) -> None:
        session = _mock_session()
        session.execute = AsyncMock()

        repo = RedemptionRequestRepository(MagicMock())
        await repo.update_state(
            "req-1", "validated", session=session, earliest_redemption_date=date(2026, 6, 1)
        )

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_by_state(self) -> None:
        session = _mock_session()
        row1 = MagicMock()
        row1.state = "pending_validation"
        row1.cnt = 3
        row2 = MagicMock()
        row2.state = "validated"
        row2.cnt = 1
        session.execute = AsyncMock(return_value=iter([row1, row2]))

        repo = RedemptionRequestRepository(MagicMock())
        result = await repo.count_by_state(session=session)

        assert result == {"pending_validation": 3, "validated": 1}


# ---------------------------------------------------------------------------
#  SubscriptionRequestRepository
# ---------------------------------------------------------------------------


class TestSubscriptionRequestRepository:
    @pytest.mark.asyncio
    async def test_save(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=SubscriptionRequestRecord)

        repo = SubscriptionRequestRepository(MagicMock())
        await repo.save(record, session=session)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = MagicMock(spec=SubscriptionRequestRecord)
        session.execute = AsyncMock(return_value=result_mock)

        repo = SubscriptionRequestRepository(MagicMock())
        result = await repo.get_by_id("req-1", session=session)

        assert result is not None

    @pytest.mark.asyncio
    async def test_list_by_state(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [MagicMock(spec=SubscriptionRequestRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = SubscriptionRequestRepository(MagicMock())
        result = await repo.list_by_state("pending_kyc", session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_by_investor(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = SubscriptionRequestRepository(MagicMock())
        result = await repo.list_by_investor("inv-1", session=session)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_by_dealing_date(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = SubscriptionRequestRepository(MagicMock())
        result = await repo.list_by_dealing_date(date(2026, 6, 30), session=session)

        assert result == []

    @pytest.mark.asyncio
    async def test_update_state(self) -> None:
        session = _mock_session()
        session.execute = AsyncMock()

        repo = SubscriptionRequestRepository(MagicMock())
        await repo.update_state("req-1", "kyc_approved", session=session, kyc_decision_by="analyst")

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_by_state(self) -> None:
        session = _mock_session()
        row1 = MagicMock()
        row1.state = "pending_kyc"
        row1.cnt = 5
        session.execute = AsyncMock(return_value=iter([row1]))

        repo = SubscriptionRequestRepository(MagicMock())
        result = await repo.count_by_state(session=session)

        assert result == {"pending_kyc": 5}
