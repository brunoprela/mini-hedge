"""Edge-case tests for RiskSnapshotService — snapshot history, FX conversion, limit breach."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.risk_engine.services.snapshot import RiskSnapshotService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_position(iid: str, qty: Decimal, mv: Decimal, currency: str = "USD"):
    pos = MagicMock()
    pos.instrument_id = iid
    pos.quantity = qty
    pos.market_value = mv
    pos.currency = currency
    return pos


def _mock_instrument(
    ticker: str, sector: str = "Technology", vol: float = 0.25, drift: float = 0.08
):
    inst = MagicMock()
    inst.ticker = ticker
    inst.sector = sector
    inst.annual_volatility = vol
    inst.annual_drift = drift
    return inst


def _make_service(
    *,
    positions=None,
    instruments=None,
    event_bus=None,
    fx_converter=None,
    var_limit_pct: float = 5.0,
) -> tuple[RiskSnapshotService, dict]:
    snapshot_repo = AsyncMock()
    snapshot_repo.get_latest_snapshot.return_value = None

    async def _save_snapshot(record, *, session=None):
        if record.id is None:
            record.id = uuid4()

    snapshot_repo.save_snapshot.side_effect = _save_snapshot

    var_result_repo = AsyncMock()
    var_contribution_repo = AsyncMock()
    stress_result_repo = AsyncMock()
    stress_impact_repo = AsyncMock()
    factor_repo = AsyncMock()

    position_service = AsyncMock()
    position_service.get_by_portfolio.return_value = positions or []

    market_data_service = AsyncMock()

    security_master_service = AsyncMock()
    security_master_service.get_all_active.return_value = instruments or [
        _mock_instrument("AAPL", "Technology"),
        _mock_instrument("JNJ", "Healthcare"),
    ]

    svc = RiskSnapshotService(
        snapshot_repo=snapshot_repo,
        var_result_repo=var_result_repo,
        var_contribution_repo=var_contribution_repo,
        stress_result_repo=stress_result_repo,
        stress_impact_repo=stress_impact_repo,
        factor_repo=factor_repo,
        position_service=position_service,
        market_data_service=market_data_service,
        security_master_service=security_master_service,
        event_bus=event_bus,
        fx_converter=fx_converter,
        var_limit_pct=var_limit_pct,
    )
    deps = {
        "snapshot_repo": snapshot_repo,
        "position_service": position_service,
        "security_master_service": security_master_service,
    }
    return svc, deps


# ---------------------------------------------------------------------------
# get_snapshot_history
# ---------------------------------------------------------------------------


class TestGetSnapshotHistory:
    async def test_returns_mapped_records(self) -> None:
        svc, deps = _make_service()
        record = MagicMock()
        record.id = str(uuid4())
        record.portfolio_id = str(uuid4())
        record.nav = Decimal("1000000")
        record.var_95_1d = Decimal("15000")
        record.var_99_1d = Decimal("25000")
        record.expected_shortfall_95 = Decimal("20000")
        record.max_drawdown = Decimal("0.05")
        record.sharpe_ratio = Decimal("1.5")
        record.snapshot_at = datetime.now(UTC)

        deps["snapshot_repo"].get_snapshot_history.return_value = [record]

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 12, 31, tzinfo=UTC)
        results = await svc.get_snapshot_history(uuid4(), start, end)

        assert len(results) == 1
        assert results[0].nav == Decimal("1000000")

    async def test_empty_history(self) -> None:
        svc, deps = _make_service()
        deps["snapshot_repo"].get_snapshot_history.return_value = []

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 12, 31, tzinfo=UTC)
        results = await svc.get_snapshot_history(uuid4(), start, end)

        assert results == []


# ---------------------------------------------------------------------------
# FX conversion in _build_risk_inputs
# ---------------------------------------------------------------------------


class TestFXConversion:
    async def test_fx_converter_used_for_non_base_currency(self) -> None:
        fx = MagicMock()
        fx.convert.return_value = Decimal("600000")  # converted value

        positions = [
            _mock_position("AAPL", Decimal("100"), Decimal("500000"), currency="EUR"),
        ]
        instruments = [_mock_instrument("AAPL", "Technology")]

        svc, deps = _make_service(
            positions=positions,
            instruments=instruments,
            fx_converter=fx,
        )

        result = await svc.calculate_var(uuid4())

        # FX converter should have been called
        fx.convert.assert_called_once()
        assert result.var_amount >= 0

    async def test_fx_converter_returns_none_uses_original(self) -> None:
        fx = MagicMock()
        fx.convert.return_value = None  # conversion failed

        positions = [
            _mock_position("AAPL", Decimal("100"), Decimal("500000"), currency="GBP"),
        ]
        instruments = [_mock_instrument("AAPL", "Technology")]

        svc, deps = _make_service(
            positions=positions,
            instruments=instruments,
            fx_converter=fx,
        )

        result = await svc.calculate_var(uuid4())

        fx.convert.assert_called_once()
        # Should still produce a valid result using original value
        assert result.var_amount >= 0

    async def test_base_currency_skips_fx(self) -> None:
        fx = MagicMock()

        positions = [
            _mock_position("AAPL", Decimal("100"), Decimal("500000"), currency="USD"),
        ]
        instruments = [_mock_instrument("AAPL", "Technology")]

        svc, deps = _make_service(
            positions=positions,
            instruments=instruments,
            fx_converter=fx,
        )

        await svc.calculate_var(uuid4())

        # Should NOT call convert for base currency position
        fx.convert.assert_not_called()


# ---------------------------------------------------------------------------
# take_snapshot — limit breach path
# ---------------------------------------------------------------------------


class TestTakeSnapshotLimitBreach:
    async def test_limit_breach_publishes_event(self) -> None:
        event_bus = AsyncMock()

        positions = [
            _mock_position("AAPL", Decimal("100"), Decimal("500000")),
            _mock_position("JNJ", Decimal("200"), Decimal("300000")),
        ]

        svc, deps = _make_service(
            positions=positions,
            event_bus=event_bus,
            var_limit_pct=0.001,  # very low limit to trigger breach
        )

        await svc.take_snapshot(uuid4(), fund_slug="alpha")

        # With such a low limit, the breach event should have been published
        # We check that publish was called at least twice (risk.updated + breach)
        assert event_bus.publish.call_count >= 2

    async def test_no_breach_when_below_limit(self) -> None:
        event_bus = AsyncMock()

        positions = [
            _mock_position("AAPL", Decimal("100"), Decimal("500000")),
        ]

        svc, deps = _make_service(
            positions=positions,
            event_bus=event_bus,
            var_limit_pct=99.0,  # very high limit — no breach
        )

        await svc.take_snapshot(uuid4(), fund_slug="alpha")

        # Only risk.updated event, no breach
        assert event_bus.publish.call_count == 1


# ---------------------------------------------------------------------------
# _build_returns_matrix with FX adjustment
# ---------------------------------------------------------------------------


class TestBuildReturnsMatrixFX:
    async def test_fx_adjusted_returns_for_non_base_currency(self) -> None:
        fx = MagicMock()
        fx.convert.return_value = Decimal("600000")

        positions = [
            _mock_position("AAPL", Decimal("100"), Decimal("500000"), currency="EUR"),
            _mock_position("JNJ", Decimal("200"), Decimal("300000"), currency="USD"),
        ]
        instruments = [
            _mock_instrument("AAPL", "Technology"),
            _mock_instrument("JNJ", "Healthcare"),
        ]

        svc, deps = _make_service(
            positions=positions,
            instruments=instruments,
            fx_converter=fx,
        )

        # Just verify it runs without error and produces a valid factor model
        result = await svc.calculate_factor_model(uuid4())
        assert result.total_risk >= 0
