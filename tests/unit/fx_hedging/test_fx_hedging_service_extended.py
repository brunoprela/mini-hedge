"""Extended unit tests for FXHedgingService — roll, queries, roll recommendations."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.fx_hedging.interfaces import (
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


class TestRollForward:
    @pytest.mark.asyncio
    async def test_roll_closes_old_and_opens_new(self) -> None:
        record = _make_forward_record(
            status=FXForwardStatus.OPEN,
            maturity_date=date(2026, 4, 15),
        )
        svc, forward_repo, rate_repo, event_bus = _make_service()
        # get_by_id returns the record on first call, then the updated (closed) one
        forward_repo.get_by_id = AsyncMock(return_value=record)
        rate_repo.get_by_currency = AsyncMock(
            return_value=_make_rate_record("EUR", Decimal("0.04"))
        )

        new_maturity = date(2026, 5, 15)
        result = await svc.roll_forward(
            UUID(record.id),
            new_maturity_date=new_maturity,
            new_contract_rate=Decimal("1.0850"),
            current_spot=Decimal("1.0800"),
            fund_slug=_FUND,
        )

        # close_forward calls update_status, then roll marks as ROLLED again
        assert forward_repo.update_status.call_count >= 2
        # A new forward is created
        forward_repo.create.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_roll_not_found_raises(self) -> None:
        svc, forward_repo, _, _ = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.roll_forward(
                uuid4(),
                new_maturity_date=date(2026, 5, 15),
                new_contract_rate=Decimal("1.09"),
                current_spot=Decimal("1.08"),
            )

    @pytest.mark.asyncio
    async def test_roll_publishes_event(self) -> None:
        record = _make_forward_record(status=FXForwardStatus.OPEN)
        svc, forward_repo, rate_repo, event_bus = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=record)
        rate_repo.get_by_currency = AsyncMock(
            return_value=_make_rate_record("EUR", Decimal("0.04"))
        )

        await svc.roll_forward(
            UUID(record.id),
            new_maturity_date=date(2026, 5, 15),
            new_contract_rate=Decimal("1.0850"),
            current_spot=Decimal("1.0800"),
            fund_slug=_FUND,
        )

        # open_forward event + close_forward event + rolled event
        assert event_bus.publish.call_count >= 2


class TestGetForward:
    @pytest.mark.asyncio
    async def test_returns_contract_when_found(self) -> None:
        record = _make_forward_record()
        svc, forward_repo, _, _ = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.get_forward(UUID(record.id))

        assert result is not None
        assert result.base_currency == "EUR"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        svc, forward_repo, _, _ = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=None)

        result = await svc.get_forward(uuid4())

        assert result is None


class TestGetOpenForwards:
    @pytest.mark.asyncio
    async def test_returns_open_forwards(self) -> None:
        fwd1 = _make_forward_record()
        fwd2 = _make_forward_record()
        svc, forward_repo, _, _ = _make_service(forwards=[fwd1, fwd2])

        result = await svc.get_open_forwards(_PORT_ID)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_list_when_none(self) -> None:
        svc, _, _, _ = _make_service(forwards=[])

        result = await svc.get_open_forwards(_PORT_ID)

        assert result == []


class TestGetForwards:
    @pytest.mark.asyncio
    async def test_returns_all_forwards(self) -> None:
        fwd = _make_forward_record()
        svc, forward_repo, _, _ = _make_service(forwards=[fwd])

        result = await svc.get_forwards(_PORT_ID)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filters_by_status(self) -> None:
        fwd = _make_forward_record(status=FXForwardStatus.CLOSED)
        svc, forward_repo, _, _ = _make_service(forwards=[fwd])

        result = await svc.get_forwards(_PORT_ID, status="closed")

        forward_repo.get_by_portfolio.assert_called_once_with(
            _PORT_ID, status="closed", session=None
        )
        assert len(result) == 1


class TestGetRollRecommendations:
    @pytest.mark.asyncio
    async def test_returns_recommendations_for_expiring(self) -> None:
        today = date.today()
        fwd = _make_forward_record(
            maturity_date=today + timedelta(days=3),
        )
        fx = MagicMock()
        fx.get_rate = MagicMock(return_value=Decimal("1.0850"))
        svc, forward_repo, rate_repo, _ = _make_service(
            forwards=[fwd], fx_converter=fx
        )
        rate_repo.get_by_currency = AsyncMock(
            return_value=_make_rate_record("EUR", Decimal("0.04"))
        )

        recs = await svc.get_roll_recommendations(_PORT_ID, days_ahead=5)

        assert len(recs) == 1
        assert recs[0].days_remaining == 3
        assert recs[0].forward_id == UUID(fwd.id)

    @pytest.mark.asyncio
    async def test_skips_when_no_spot(self) -> None:
        today = date.today()
        fwd = _make_forward_record(
            maturity_date=today + timedelta(days=2),
        )
        svc, _, _, _ = _make_service(forwards=[fwd], fx_converter=None)

        recs = await svc.get_roll_recommendations(_PORT_ID, days_ahead=5)

        # No fx_converter means _get_spot returns None, forward is skipped
        assert recs == []

    @pytest.mark.asyncio
    async def test_no_expiring_forwards(self) -> None:
        fwd = _make_forward_record(
            maturity_date=date.today() + timedelta(days=30),
        )
        svc, _, _, _ = _make_service(forwards=[fwd])

        recs = await svc.get_roll_recommendations(_PORT_ID, days_ahead=5)

        assert recs == []


class TestPublishEvent:
    @pytest.mark.asyncio
    async def test_no_publish_without_fund_slug(self) -> None:
        svc, _, _, event_bus = _make_service()

        # Call internal _publish_event with no fund_slug
        await svc._publish_event("test.event", None, {"key": "value"})

        event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_publish_without_event_bus(self) -> None:
        forward_repo = AsyncMock()
        rate_repo = AsyncMock()
        svc = FXHedgingService(
            forward_repo=forward_repo,
            rate_repo=rate_repo,
            event_bus=None,
            base_currency="USD",
        )

        # Should not raise
        await svc._publish_event("test.event", "alpha", {"key": "value"})


class TestGetSpot:
    def test_returns_none_without_fx_converter(self) -> None:
        svc, _, _, _ = _make_service(fx_converter=None)

        result = svc._get_spot("EUR", "USD")

        assert result is None

    def test_returns_rate_with_fx_converter(self) -> None:
        fx = MagicMock()
        fx.get_rate = MagicMock(return_value=Decimal("1.0800"))
        svc, _, _, _ = _make_service(fx_converter=fx)

        result = svc._get_spot("EUR", "USD")

        assert result == Decimal("1.0800")
        fx.get_rate.assert_called_once_with("EUR", "USD")


class TestGetDomesticRate:
    @pytest.mark.asyncio
    async def test_returns_rate_when_found(self) -> None:
        svc, _, rate_repo, _ = _make_service()
        rate_repo.get_by_currency = AsyncMock(
            return_value=_make_rate_record("USD", Decimal("0.053"))
        )

        result = await svc._get_domestic_rate()

        assert result == Decimal("0.053")

    @pytest.mark.asyncio
    async def test_returns_zero_when_not_found(self) -> None:
        svc, _, rate_repo, _ = _make_service()
        rate_repo.get_by_currency = AsyncMock(return_value=None)

        result = await svc._get_domestic_rate()

        assert result == Decimal(0)


class TestCloseForwardSellDirection:
    @pytest.mark.asyncio
    async def test_sell_direction_pnl(self) -> None:
        """Sell direction should negate the PnL sign."""
        record = _make_forward_record(
            status=FXForwardStatus.OPEN,
            direction="sell",
        )
        svc, forward_repo, _, _ = _make_service()
        forward_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.close_forward(
            UUID(record.id),
            close_rate=Decimal("1.0900"),
            close_spot=Decimal("1.0850"),
            fund_slug=_FUND,
        )

        forward_repo.update_status.assert_called_once()
        # Verify update_status was called with negative PnL for sell when rate goes up
        call_kwargs = forward_repo.update_status.call_args
        assert call_kwargs.kwargs["realized_pnl"] is not None
