"""Edge-case tests for LiquidityMarginService — cash service path, margin call logging."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import uuid4

import pytest

from app.modules.risk_engine.services.liquidity_margin import LiquidityMarginService

_PORT_ID = uuid4()


def _make_position(
    instrument_id: str = "AAPL",
    market_value: Decimal = Decimal("5000000"),
    current_price: Decimal = Decimal("250"),
    quantity: Decimal = Decimal("20000"),
) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.market_value = market_value
    p.current_price = current_price
    p.quantity = quantity
    return p


def _make_instrument(
    ticker: str = "AAPL",
    avg_daily_volume: int = 50000000,
    asset_class: str = "equity",
) -> MagicMock:
    i = MagicMock()
    i.ticker = ticker
    i.avg_daily_volume = avg_daily_volume
    i.asset_class = asset_class
    return i


def _make_service(
    positions: list | None = None,
    instruments: dict[str, MagicMock] | None = None,
    *,
    cash_service: AsyncMock | None = None,
) -> tuple[LiquidityMarginService, AsyncMock, AsyncMock]:
    liquidity_repo = AsyncMock()
    liquidity_repo.save_liquidity_profile = AsyncMock()
    margin_repo = AsyncMock()
    margin_repo.save_margin_requirement = AsyncMock()

    position_service = AsyncMock()
    position_service.get_positions = AsyncMock(return_value=positions or [])

    sm_service = AsyncMock()

    async def _get_instrument(instrument_id: str, **kw) -> MagicMock | None:
        if instruments and instrument_id in instruments:
            return instruments[instrument_id]
        return _make_instrument(instrument_id)

    sm_service.get_instrument = AsyncMock(side_effect=_get_instrument)

    svc = LiquidityMarginService(
        liquidity_repo=liquidity_repo,
        margin_repo=margin_repo,
        position_service=position_service,
        security_master_service=sm_service,
    )

    if cash_service is not None:
        svc._cash_service = cash_service

    return svc, liquidity_repo, margin_repo


class TestCalculateMarginCashService:
    async def test_uses_cash_service_when_available(self) -> None:
        """When _cash_service is set, it should use its balance."""
        cash_svc = AsyncMock()
        cash_svc.get_total_balance.return_value = Decimal("2000000")

        positions = [_make_position("AAPL", Decimal("5000000"))]
        svc, _, margin_repo = _make_service(positions, cash_service=cash_svc)

        result = await svc.calculate_margin(_PORT_ID)

        assert result.portfolio_id == _PORT_ID
        cash_svc.get_total_balance.assert_called_once()
        # margin_available should be 2M from cash service
        assert result.margin_available == Decimal("2000000")
        margin_repo.save_margin_requirement.assert_called_once()

    async def test_cash_service_failure_falls_back(self) -> None:
        """When cash service raises, should fall back to estimated cash."""
        cash_svc = AsyncMock()
        cash_svc.get_total_balance.side_effect = Exception("connection error")

        positions = [_make_position("AAPL", Decimal("5000000"))]
        svc, _, margin_repo = _make_service(positions, cash_service=cash_svc)

        result = await svc.calculate_margin(_PORT_ID)

        assert result.portfolio_id == _PORT_ID
        # Should still work with estimated cash (60% of NAV)
        margin_repo.save_margin_requirement.assert_called_once()

    async def test_margin_call_logged(self) -> None:
        """Margin call should be triggered when cash is insufficient."""
        # With 100M position and only 100K cash, margin call should trigger
        positions = [_make_position("AAPL", Decimal("100000000"))]
        cash_svc = AsyncMock()
        cash_svc.get_total_balance.return_value = Decimal("100000")

        svc, _, margin_repo = _make_service(positions, cash_service=cash_svc)

        result = await svc.calculate_margin(_PORT_ID)

        assert result.margin_call_triggered is True
        margin_repo.save_margin_requirement.assert_called_once()
