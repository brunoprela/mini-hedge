"""Unit tests for FXHedgingService — forward lifecycle, MTM, recommendations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.fx_hedging.interfaces import (
    FXForwardCreate,
    FXForwardDirection,
    FXForwardStatus,
)
from app.modules.fx_hedging.services.fx_hedging import FXHedgingService

_PORT_ID = uuid4()
_FUND = "alpha"


def _make_forward_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.id = str(uuid4())
    r.portfolio_id = str(_PORT_ID)
    r.base_currency = "EUR"
    r.quote_currency = "USD"
    r.direction = "buy"
    r.notional = Decimal("1000000")
    r.contract_rate = Decimal("1.0800")
    r.spot_at_inception = Decimal("1.0750")
    r.trade_date = date(2026, 3, 15)
    r.maturity_date = date(2026, 4, 15)
    r.status = FXForwardStatus.OPEN
    r.counterparty = "Goldman Sachs"
    r.roll_from_id = None
    r.mtm_value = None
    r.mtm_timestamp = None
    r.created_at = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _make_rate_record(currency: str = "USD", rate: Decimal = Decimal("0.05")) -> MagicMock:
    r = MagicMock()
    r.currency = currency
    r.rate = rate
    r.tenor_days = 30
    r.source = "manual"
    return r


def _make_service(
    forwards: list | None = None,
    fx_converter: MagicMock | None = None,
) -> tuple[FXHedgingService, AsyncMock, AsyncMock, AsyncMock]:
    forward_repo = AsyncMock()
    def _assign_id(r, **kw):
        if r.id is None or not isinstance(r.id, str):
            r.id = str(uuid4())
        return r

    forward_repo.create = AsyncMock(side_effect=_assign_id)
    forward_repo.get_by_id = AsyncMock(return_value=None)
    forward_repo.get_open_by_portfolio = AsyncMock(return_value=forwards or [])
    forward_repo.get_by_portfolio = AsyncMock(return_value=forwards or [])
    forward_repo.update_status = AsyncMock()
    forward_repo.update_mtm = AsyncMock()

    rate_repo = AsyncMock()
    rate_repo.get_by_currency = AsyncMock(return_value=_make_rate_record())
    rate_repo.get_all = AsyncMock(return_value=[])
    rate_repo.upsert = AsyncMock()

    event_bus = AsyncMock()

    svc = FXHedgingService(
        forward_repo=forward_repo,
        rate_repo=rate_repo,
        event_bus=event_bus,
        fx_converter=fx_converter,
        base_currency="USD",
    )
    return svc, forward_repo, rate_repo, event_bus


class TestOpenForward:
    @pytest.mark.asyncio
    async def test_opens_forward_contract(self) -> None:
        svc, forward_repo, _, _ = _make_service()
        create = FXForwardCreate(
            portfolio_id=_PORT_ID,
            base_currency="EUR",
            quote_currency="USD",
            direction=FXForwardDirection.BUY,
            notional=Decimal("1000000"),
            contract_rate=Decimal("1.0800"),
            spot_at_inception=Decimal("1.0750"),
            trade_date=date(2026, 4, 1),
            maturity_date=date(2026, 5, 1),
            counterparty="Goldman Sachs",
        )

        result = await svc.open_forward(create, fund_slug=_FUND)

        forward_repo.create.assert_called_once()
        assert result.notional == Decimal("1000000")
        assert result.status == FXForwardStatus.OPEN

    @pytest.mark.asyncio
    async def test_publishes_event_on_open(self) -> None:
        svc, _, _, event_bus = _make_service()
        create = FXForwardCreate(
            portfolio_id=_PORT_ID,
            base_currency="EUR",
            quote_currency="USD",
            direction=FXForwardDirection.BUY,
            notional=Decimal("500000"),
            contract_rate=Decimal("1.0800"),
            spot_at_inception=Decimal("1.0750"),
            trade_date=date(2026, 4, 1),
            maturity_date=date(2026, 5, 1),
        )

        await svc.open_forward(create, fund_slug=_FUND)

        event_bus.publish.assert_called_once()


class TestCloseForward:
    @pytest.mark.asyncio
    async def test_closes_open_forward(self) -> None:
        record = _make_forward_record(status=FXForwardStatus.OPEN)
        svc, forward_repo, _, _ = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.close_forward(
            UUID(record.id),
            close_rate=Decimal("1.0900"),
            close_spot=Decimal("1.0850"),
            fund_slug=_FUND,
        )

        forward_repo.update_status.assert_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_close_not_found_raises(self) -> None:
        svc, forward_repo, _, _ = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.close_forward(uuid4(), close_rate=Decimal("1.09"), close_spot=Decimal("1.08"))

    @pytest.mark.asyncio
    async def test_close_already_closed_raises(self) -> None:
        record = _make_forward_record(status=FXForwardStatus.CLOSED)
        svc, forward_repo, _, _ = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=record)

        with pytest.raises(ValueError, match="cannot close"):
            await svc.close_forward(
                UUID(record.id), close_rate=Decimal("1.09"), close_spot=Decimal("1.08")
            )


class TestMarkToMarket:
    @pytest.mark.asyncio
    async def test_mtm_updates_all_open_forwards(self) -> None:
        fwd = _make_forward_record()
        fx = MagicMock()
        fx.get_rate = MagicMock(return_value=Decimal("1.0850"))
        svc, forward_repo, _, _ = _make_service(forwards=[fwd], fx_converter=fx)

        results = await svc.mark_to_market_all(_PORT_ID, fund_slug=_FUND)

        assert len(results) == 1
        forward_repo.update_mtm.assert_called_once()

    @pytest.mark.asyncio
    async def test_mtm_skips_when_no_spot(self) -> None:
        fwd = _make_forward_record()
        fx = MagicMock()
        fx.get_rate = MagicMock(return_value=None)
        svc, forward_repo, _, _ = _make_service(forwards=[fwd], fx_converter=fx)

        results = await svc.mark_to_market_all(_PORT_ID)

        forward_repo.update_mtm.assert_not_called()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_mtm_no_forwards(self) -> None:
        svc, _, _, _ = _make_service(forwards=[])

        results = await svc.mark_to_market_all(_PORT_ID)

        assert results == []


class TestGetSummary:
    @pytest.mark.asyncio
    async def test_summary_with_forwards(self) -> None:
        fwd1 = _make_forward_record(
            notional=Decimal("1000000"),
            mtm_value=Decimal("5000"),
            base_currency="EUR",
            quote_currency="USD",
            maturity_date=date(2026, 4, 14),
        )
        fwd2 = _make_forward_record(
            notional=Decimal("2000000"),
            mtm_value=Decimal("-3000"),
            base_currency="GBP",
            quote_currency="USD",
            maturity_date=date(2026, 5, 20),
        )
        svc, _, _, _ = _make_service(forwards=[fwd1, fwd2])

        result = await svc.get_summary(_PORT_ID)

        assert result.open_forwards == 2
        assert result.total_notional == Decimal("3000000")
        assert result.total_mtm == Decimal("2000")

    @pytest.mark.asyncio
    async def test_empty_summary(self) -> None:
        svc, _, _, _ = _make_service(forwards=[])

        result = await svc.get_summary(_PORT_ID)

        assert result.open_forwards == 0
        assert result.total_notional == Decimal(0)


class TestHedgeRecommendations:
    @pytest.mark.asyncio
    async def test_generates_recommendations(self) -> None:
        fx = MagicMock()
        fx.get_rate = MagicMock(return_value=Decimal("1.0800"))
        svc, _, rate_repo, _ = _make_service(fx_converter=fx)
        rate_repo.get_by_currency = AsyncMock(return_value=_make_rate_record("EUR", Decimal("0.04")))

        recs = await svc.get_hedge_recommendations(
            _PORT_ID,
            {"EUR": Decimal("5000000")},
            fund_slug=_FUND,
        )

        assert len(recs) == 1
        assert recs[0].direction == "sell"
        assert recs[0].notional > Decimal(0)

    @pytest.mark.asyncio
    async def test_no_recommendations_for_base_currency(self) -> None:
        svc, _, _, _ = _make_service()

        recs = await svc.get_hedge_recommendations(
            _PORT_ID,
            {"USD": Decimal("10000000")},
        )

        assert recs == []


class TestInterestRates:
    @pytest.mark.asyncio
    async def test_set_rate(self) -> None:
        svc, _, rate_repo, _ = _make_service()

        await svc.set_interest_rate("EUR", Decimal("0.0375"))

        rate_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rates(self) -> None:
        svc, _, rate_repo, _ = _make_service()
        rate_repo.get_all = AsyncMock(return_value=[_make_rate_record()])

        result = await svc.get_interest_rates()

        assert len(result) == 1
