"""Additional unit tests for QuantResearchService — covers create_factor,
list_factors, decompose_portfolio, get_regime_history, get_current_regime,
and deeper analyze_factor branches (correlation, exposures, max-drawdown).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.quant_research.core.factor_engine import (
    compute_momentum_factor,
)
from app.modules.quant_research.core.regime_detector import RegimeDetector
from app.modules.quant_research.interfaces import (
    FactorType,
    RegimeType,
)
from app.modules.quant_research.services import QuantResearchService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date(2026, 4, 12)


def _make_factor_record(**overrides) -> MagicMock:
    record = MagicMock()
    record.id = overrides.get("id", str(uuid4()))
    record.name = overrides.get("name", "momentum")
    record.factor_type = overrides.get("factor_type", FactorType.MOMENTUM.value)
    record.description = overrides.get("description", "")
    record.formula = overrides.get("formula", "")
    record.parameters = overrides.get("parameters", {})
    record.is_active = overrides.get("is_active", True)
    return record


def _make_return_record(return_pct: Decimal, cum: Decimal, d: date) -> MagicMock:
    r = MagicMock()
    r.return_pct = return_pct
    r.cumulative_return = cum
    r.return_date = d
    return r


def _make_exposure_record(
    instrument_id: str, exposure: Decimal, z_score: Decimal, as_of_date: date
) -> MagicMock:
    r = MagicMock()
    r.instrument_id = instrument_id
    r.exposure = exposure
    r.z_score = z_score
    r.as_of_date = as_of_date
    r.factor_id = str(uuid4())
    return r


def _make_regime_snapshot(
    regime_type: str = "bull",
    confidence: Decimal = Decimal("0.75"),
    start_date: date = date(2026, 1, 1),
    end_date: date | None = None,
    indicators: dict | None = None,
) -> MagicMock:
    r = MagicMock()
    r.regime_type = regime_type
    r.confidence = confidence
    r.start_date = start_date
    r.end_date = end_date
    r.indicators = indicators or {"volatility": "0.10", "trend": "0.05"}
    r.created_at = MagicMock()
    return r


def _make_service(
    factor_def_repo: AsyncMock | None = None,
    factor_exp_repo: AsyncMock | None = None,
    factor_ret_repo: AsyncMock | None = None,
    regime_repo: AsyncMock | None = None,
    regime_detector: RegimeDetector | None = None,
    event_bus: AsyncMock | None = None,
) -> QuantResearchService:
    return QuantResearchService(
        factor_def_repo=factor_def_repo or AsyncMock(),
        factor_exp_repo=factor_exp_repo or AsyncMock(),
        factor_ret_repo=factor_ret_repo or AsyncMock(),
        regime_repo=regime_repo or AsyncMock(),
        factor_engine_fns={
            FactorType.MOMENTUM.value: compute_momentum_factor,
        },
        regime_detector=regime_detector or RegimeDetector(),
        session_factory=MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# TestCreateFactor
# ---------------------------------------------------------------------------


def _patch_record_id(repo_mock: AsyncMock) -> None:
    """Make the repo.create call set a valid id on the record."""

    async def _create_side_effect(record, **kwargs):
        if record.id is None:
            record.id = str(uuid4())

    repo_mock.create.side_effect = _create_side_effect


class TestCreateFactor:
    async def test_create_factor_calls_repo_and_returns_definition(self):
        factor_def_repo = AsyncMock()
        _patch_record_id(factor_def_repo)
        svc = _make_service(factor_def_repo=factor_def_repo)

        result = await svc.create_factor(
            name="momentum",
            factor_type=FactorType.MOMENTUM,
            description="12m momentum",
            formula="ret(252) - ret(21)",
            parameters={"lookback": 252},
        )

        assert result.name == "momentum"
        assert result.factor_type == FactorType.MOMENTUM
        assert result.description == "12m momentum"
        assert result.formula == "ret(252) - ret(21)"
        assert result.parameters == {"lookback": 252}
        assert result.is_active is True
        factor_def_repo.create.assert_called_once()

    async def test_create_factor_defaults_optional_fields(self):
        factor_def_repo = AsyncMock()
        _patch_record_id(factor_def_repo)
        svc = _make_service(factor_def_repo=factor_def_repo)

        result = await svc.create_factor(
            name="custom_factor",
            factor_type=FactorType.CUSTOM,
        )

        assert result.name == "custom_factor"
        assert result.description == ""
        assert result.formula == ""
        assert result.parameters == {}


# ---------------------------------------------------------------------------
# TestListFactors
# ---------------------------------------------------------------------------


class TestListFactors:
    async def test_list_factors_returns_definitions(self):
        factor_def_repo = AsyncMock()
        records = [
            _make_factor_record(name="momentum", factor_type=FactorType.MOMENTUM.value),
            _make_factor_record(name="value", factor_type=FactorType.VALUE.value),
        ]
        factor_def_repo.list_all.return_value = records
        svc = _make_service(factor_def_repo=factor_def_repo)

        result = await svc.list_factors()

        assert len(result) == 2
        assert result[0].name == "momentum"
        assert result[1].name == "value"

    async def test_list_factors_empty(self):
        factor_def_repo = AsyncMock()
        factor_def_repo.list_all.return_value = []
        svc = _make_service(factor_def_repo=factor_def_repo)

        result = await svc.list_factors()

        assert result == []


# ---------------------------------------------------------------------------
# TestDecomposePortfolio
# ---------------------------------------------------------------------------


class TestDecomposePortfolio:
    async def test_decompose_returns_factor_contributions(self):
        factor_def_repo = AsyncMock()
        factor_exp_repo = AsyncMock()

        # Two factors found
        mom_record = _make_factor_record(name="momentum", id="factor-mom-id")
        val_record = _make_factor_record(name="value", id="factor-val-id")
        factor_def_repo.get_by_name.side_effect = lambda name, **kw: {
            "momentum": mom_record,
            "value": val_record,
        }.get(name)

        # Exposure records for each factor
        mom_exposures = [
            _make_exposure_record("AAPL", Decimal("1.2"), Decimal("1.2"), TODAY),
            _make_exposure_record("MSFT", Decimal("0.5"), Decimal("0.5"), TODAY),
        ]
        val_exposures = [
            _make_exposure_record("AAPL", Decimal("-0.3"), Decimal("-0.3"), TODAY),
            _make_exposure_record("MSFT", Decimal("0.8"), Decimal("0.8"), TODAY),
        ]
        factor_exp_repo.get_by_factor_date.side_effect = lambda fid, dt, **kw: {
            "factor-mom-id": mom_exposures,
            "factor-val-id": val_exposures,
        }.get(fid, [])

        svc = _make_service(factor_def_repo=factor_def_repo, factor_exp_repo=factor_exp_repo)

        result = await svc.decompose_portfolio(
            portfolio_weights={"AAPL": Decimal("0.6"), "MSFT": Decimal("0.4")},
            factor_names=["momentum", "value"],
        )

        assert result.factors is not None
        assert len(result.factors) == 2
        assert result.residual_pct is not None
        assert result.explained_variance_pct is not None

    async def test_decompose_skips_unknown_factor(self):
        factor_def_repo = AsyncMock()
        factor_exp_repo = AsyncMock()

        factor_def_repo.get_by_name.return_value = None
        factor_exp_repo.get_by_factor_date.return_value = []

        svc = _make_service(factor_def_repo=factor_def_repo, factor_exp_repo=factor_exp_repo)

        result = await svc.decompose_portfolio(
            portfolio_weights={"AAPL": Decimal("1.0")},
            factor_names=["nonexistent"],
        )

        # Unknown factor is skipped, so no factor contributions
        assert len(result.factors) == 0


# ---------------------------------------------------------------------------
# TestGetRegimeHistory
# ---------------------------------------------------------------------------


class TestGetRegimeHistory:
    async def test_returns_market_regime_list(self):
        regime_repo = AsyncMock()
        regime_repo.get_history.return_value = [
            _make_regime_snapshot(regime_type="bull", start_date=date(2026, 1, 1)),
            _make_regime_snapshot(regime_type="bear", start_date=date(2025, 6, 1)),
        ]
        svc = _make_service(regime_repo=regime_repo)

        result = await svc.get_regime_history(limit=50)

        assert len(result) == 2
        assert result[0].regime_type == RegimeType.BULL
        assert result[1].regime_type == RegimeType.BEAR
        regime_repo.get_history.assert_called_once_with(limit=50, session=None)


# ---------------------------------------------------------------------------
# TestGetCurrentRegime
# ---------------------------------------------------------------------------


class TestGetCurrentRegime:
    async def test_returns_current_regime(self):
        regime_repo = AsyncMock()
        regime_repo.get_latest.return_value = _make_regime_snapshot(
            regime_type="high_vol",
            confidence=Decimal("0.80"),
            start_date=date(2026, 3, 1),
            indicators={"volatility": "0.30", "trend": "-0.02"},
        )
        svc = _make_service(regime_repo=regime_repo)

        result = await svc.get_current_regime()

        assert result is not None
        assert result.regime_type == RegimeType.HIGH_VOL
        assert result.confidence == Decimal("0.80")
        assert result.indicators["volatility"] == Decimal("0.30")

    async def test_returns_none_when_no_regime(self):
        regime_repo = AsyncMock()
        regime_repo.get_latest.return_value = None
        svc = _make_service(regime_repo=regime_repo)

        result = await svc.get_current_regime()

        assert result is None


# ---------------------------------------------------------------------------
# TestAnalyzeFactorDeeper — coverage for correlation, exposures, drawdown
# ---------------------------------------------------------------------------


class TestAnalyzeFactorDeeper:
    async def test_analyze_factor_with_correlation_and_exposures(self):
        """Cover the correlation matrix + top_exposures branches."""
        factor_def_repo = AsyncMock()
        factor_exp_repo = AsyncMock()
        factor_ret_repo = AsyncMock()

        mom_id = str(uuid4())
        val_id = str(uuid4())

        mom_record = _make_factor_record(name="momentum", id=mom_id)
        val_record = _make_factor_record(name="value", id=val_id)

        factor_def_repo.get_by_name.return_value = mom_record

        # Return records with varying cumulative returns (triggers drawdown logic)
        returns_data = []
        base = date(2025, 1, 1)
        cum = Decimal("1.0")
        for i in range(20):
            pct = Decimal("0.02") if i < 15 else Decimal("-0.03")
            cum = cum * (Decimal(1) + pct)
            returns_data.append(_make_return_record(pct, cum, base + timedelta(days=i)))

        factor_ret_repo.get_by_factor.side_effect = lambda fid, **kw: {
            mom_id: returns_data,
            val_id: [
                _make_return_record(Decimal("0.01"), Decimal("1.01"), base + timedelta(days=i))
                for i in range(20)
            ],
        }.get(fid, [])

        # list_all returns both factors for correlation
        factor_def_repo.list_all.return_value = [mom_record, val_record]

        # Exposure records for top_exposures branch
        factor_exp_repo.get_by_factor_date.return_value = [
            _make_exposure_record("AAPL", Decimal("1.5"), Decimal("2.0"), TODAY),
            _make_exposure_record("MSFT", Decimal("0.8"), Decimal("1.0"), TODAY),
        ]

        svc = _make_service(
            factor_def_repo=factor_def_repo,
            factor_exp_repo=factor_exp_repo,
            factor_ret_repo=factor_ret_repo,
        )

        result = await svc.analyze_factor("momentum", start_date=base, end_date=base + timedelta(days=19))

        assert result.factor_name == "momentum"
        assert result.mean_return != Decimal(0)
        assert result.volatility != Decimal(0)
        # Correlation matrix should have entries for both factors
        assert len(result.correlation_matrix) == 2
        assert "momentum" in result.correlation_matrix
        assert "value" in result.correlation_matrix
        # Top exposures should be populated
        assert len(result.top_exposures) == 2
        assert result.top_exposures[0].factor_name == "momentum"

    async def test_analyze_factor_max_drawdown_computed(self):
        """Cover the max drawdown branch with peak > 0."""
        factor_def_repo = AsyncMock()
        factor_exp_repo = AsyncMock()
        factor_ret_repo = AsyncMock()

        fid = str(uuid4())
        factor_def_repo.get_by_name.return_value = _make_factor_record(id=fid)

        # Build returns with a peak and then a decline
        base = date(2025, 1, 1)
        returns_data = []
        cum_values = [
            Decimal("1.00"), Decimal("1.05"), Decimal("1.10"), Decimal("1.15"),
            Decimal("1.20"),  # peak
            Decimal("1.10"), Decimal("1.00"), Decimal("0.90"),  # drawdown
        ]
        for i, cum in enumerate(cum_values):
            pct = (cum - cum_values[i - 1]) / cum_values[i - 1] if i > 0 else Decimal("0")
            returns_data.append(_make_return_record(pct, cum, base + timedelta(days=i)))

        factor_ret_repo.get_by_factor.return_value = returns_data
        factor_def_repo.list_all.return_value = []
        factor_exp_repo.get_by_factor_date.return_value = []

        svc = _make_service(
            factor_def_repo=factor_def_repo,
            factor_exp_repo=factor_exp_repo,
            factor_ret_repo=factor_ret_repo,
        )

        result = await svc.analyze_factor("momentum")

        # max_drawdown should be negative (representing a drop from peak)
        assert result.max_drawdown < Decimal(0)
