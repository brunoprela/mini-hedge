"""Unit tests for AttributionService — service-level orchestration tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.attribution.services.attribution import AttributionService

_PORT_ID = uuid4()


def _make_position(
    instrument_id: str,
    market_value: Decimal,
    quantity: Decimal = Decimal("100"),
    currency: str = "USD",
) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.market_value = market_value
    p.quantity = quantity
    p.currency = currency
    return p


def _make_instrument(
    ticker: str,
    sector: str = "Technology",
    annual_drift: float = 0.08,
    annual_volatility: float = 0.25,
) -> MagicMock:
    i = MagicMock()
    i.ticker = ticker
    i.sector = sector
    i.annual_drift = annual_drift
    i.annual_volatility = annual_volatility
    return i


def _make_service(
    positions: list | None = None,
    instruments: list | None = None,
) -> tuple[AttributionService, AsyncMock, AsyncMock]:
    bf_repo = AsyncMock()
    bf_repo.save = AsyncMock()
    bf_repo.get_by_portfolio = AsyncMock(return_value=[])
    bf_sector_repo = AsyncMock()
    bf_sector_repo.save_many = AsyncMock()
    bf_sector_repo.get_by_bf_result = AsyncMock(return_value=[])
    rb_repo = AsyncMock()
    rb_repo.save = AsyncMock()
    rfc_repo = AsyncMock()
    rfc_repo.save_many = AsyncMock()
    cum_repo = AsyncMock()

    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    sm_service = AsyncMock()
    sm_service.get_all_active = AsyncMock(return_value=instruments or [])

    event_bus = AsyncMock()

    svc = AttributionService(
        bf_repo=bf_repo,
        bf_sector_repo=bf_sector_repo,
        rb_repo=rb_repo,
        rfc_repo=rfc_repo,
        cum_repo=cum_repo,
        position_service=position_service,
        security_master_service=sm_service,
        event_bus=event_bus,
    )
    return svc, bf_repo, event_bus


class TestBrinsonFachler:
    @pytest.mark.asyncio
    async def test_calculates_and_persists(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("500000")),
            _make_position("MSFT", Decimal("300000")),
        ]
        instruments = [
            _make_instrument("AAPL", sector="Technology"),
            _make_instrument("MSFT", sector="Technology"),
        ]
        svc, bf_repo, _ = _make_service(positions, instruments)

        result = await svc.calculate_brinson_fachler(
            _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
        )

        assert result.portfolio_id == _PORT_ID
        assert result.period_start == date(2026, 3, 1)
        assert result.period_end == date(2026, 3, 31)
        bf_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_portfolio_returns_zeros(self) -> None:
        svc, bf_repo, _ = _make_service([], [])

        result = await svc.calculate_brinson_fachler(
            _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
        )

        assert result.active_return == Decimal(0)
        assert result.sectors == []
        bf_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_zero_quantity_positions(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("500000")),
            _make_position("MSFT", Decimal("0"), quantity=Decimal("0")),
        ]
        instruments = [
            _make_instrument("AAPL"),
            _make_instrument("MSFT"),
        ]
        svc, bf_repo, _ = _make_service(positions, instruments)

        result = await svc.calculate_brinson_fachler(
            _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
        )

        # Only AAPL is included
        bf_repo.save.assert_called_once()
        assert result.portfolio_id == _PORT_ID

    @pytest.mark.asyncio
    async def test_publishes_event(self) -> None:
        positions = [_make_position("AAPL", Decimal("500000"))]
        instruments = [_make_instrument("AAPL")]
        svc, _, event_bus = _make_service(positions, instruments)

        with patch(
            "app.shared.database.TenantSessionFactory"
        ) as mock_tsf:
            mock_tsf.current_fund_slug.return_value = "alpha"
            await svc.calculate_brinson_fachler(
                _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
            )

        event_bus.publish.assert_called_once()


class TestRiskBased:
    @pytest.mark.asyncio
    async def test_calculates_risk_based(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("500000")),
            _make_position("MSFT", Decimal("300000")),
        ]
        instruments = [
            _make_instrument("AAPL"),
            _make_instrument("MSFT"),
        ]
        svc, _, _ = _make_service(positions, instruments)

        result = await svc.calculate_risk_based(
            _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
        )

        assert result.portfolio_id == _PORT_ID
        # Systematic + idiosyncratic should sum to total
        assert result.total_pnl == pytest.approx(
            result.systematic_pnl + result.idiosyncratic_pnl, abs=Decimal("0.01")
        )

    @pytest.mark.asyncio
    async def test_empty_portfolio_returns_zeros(self) -> None:
        svc, _, _ = _make_service([], [])

        result = await svc.calculate_risk_based(
            _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
        )

        assert result.total_pnl == Decimal(0)
        assert result.factor_contributions == []


class TestCumulative:
    @pytest.mark.asyncio
    async def test_cumulative_with_no_stored_periods(self) -> None:
        """When no stored periods exist, calculates a single period first."""
        positions = [_make_position("AAPL", Decimal("500000"))]
        instruments = [_make_instrument("AAPL")]
        svc, bf_repo, _ = _make_service(positions, instruments)

        result = await svc.calculate_cumulative(
            _PORT_ID, date(2026, 1, 1), date(2026, 3, 31)
        )

        assert result.portfolio_id == _PORT_ID
        # Should have calculated at least one period
        bf_repo.save.assert_called()

    @pytest.mark.asyncio
    async def test_cumulative_with_stored_periods(self) -> None:
        """When stored periods exist, links them using Carino."""
        svc, bf_repo, _ = _make_service()

        # Mock stored BF records
        record = MagicMock()
        record.id = str(uuid4())
        record.portfolio_id = str(_PORT_ID)
        record.period_start = date(2026, 1, 1)
        record.period_end = date(2026, 1, 31)
        record.portfolio_return = Decimal("0.02")
        record.benchmark_return = Decimal("0.015")
        record.active_return = Decimal("0.005")
        record.total_allocation = Decimal("0.002")
        record.total_selection = Decimal("0.003")
        record.total_interaction = Decimal("0.000")
        record.calculated_at = MagicMock()

        bf_repo.get_by_portfolio = AsyncMock(return_value=[record])

        with patch(
            "app.shared.database.TenantSessionFactory"
        ) as mock_tsf:
            mock_tsf.current_fund_slug.return_value = "alpha"
            result = await svc.calculate_cumulative(
                _PORT_ID, date(2026, 1, 1), date(2026, 3, 31)
            )

        assert result.portfolio_id == _PORT_ID


class TestFXAttribution:
    @pytest.mark.asyncio
    async def test_fx_attribution_with_positions(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("500000"), currency="USD"),
            _make_position("VOD.L", Decimal("300000"), currency="GBP"),
        ]
        instruments = [
            _make_instrument("AAPL"),
            _make_instrument("VOD.L"),
        ]
        fx = MagicMock()
        fx.get_rate = MagicMock(return_value=Decimal("1.25"))

        svc = AttributionService(
            bf_repo=AsyncMock(),
            bf_sector_repo=AsyncMock(),
            rb_repo=AsyncMock(),
            rfc_repo=AsyncMock(),
            cum_repo=AsyncMock(),
            position_service=AsyncMock(get_by_portfolio=AsyncMock(return_value=positions)),
            security_master_service=AsyncMock(get_all_active=AsyncMock(return_value=instruments)),
            fx_converter=fx,
        )

        result = await svc.calculate_fx(
            _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
        )

        assert result.portfolio_id == _PORT_ID
        assert result.base_currency == "USD"
        # Total base return = local + fx + interaction
        total = result.total_local_return + result.total_fx_return + result.total_interaction
        assert result.total_base_return == pytest.approx(total, abs=Decimal("0.01"))

    @pytest.mark.asyncio
    async def test_fx_attribution_empty_portfolio(self) -> None:
        svc, _, _ = _make_service([], [])

        result = await svc.calculate_fx(
            _PORT_ID, date(2026, 3, 1), date(2026, 3, 31)
        )

        assert result.total_base_return == Decimal(0)
        assert result.positions == []
