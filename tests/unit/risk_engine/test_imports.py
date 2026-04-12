"""Import coverage tests for risk engine packages — repos and routes."""

from __future__ import annotations


class TestRepositoryImports:
    def test_repositories_init_exports(self) -> None:
        from app.modules.risk_engine.repositories import (
            CounterpartyExposureRepository,
            CounterpartyRepository,
            FactorExposureRepository,
            LiquidityRepository,
            MarginRepository,
            RiskSnapshotRepository,
            StressPositionImpactRepository,
            StressTestResultRepository,
            VaRContributionRepository,
            VaRResultRepository,
        )

        # Verify all classes are importable and are classes
        assert callable(CounterpartyExposureRepository)
        assert callable(CounterpartyRepository)
        assert callable(FactorExposureRepository)
        assert callable(LiquidityRepository)
        assert callable(MarginRepository)
        assert callable(RiskSnapshotRepository)
        assert callable(StressPositionImpactRepository)
        assert callable(StressTestResultRepository)
        assert callable(VaRContributionRepository)
        assert callable(VaRResultRepository)


class TestRouteImports:
    def test_routes_init_exports(self) -> None:
        from app.modules.risk_engine.routes import (
            counterparty_router,
            liquidity_margin_router,
            snapshot_router,
        )

        assert counterparty_router is not None
        assert liquidity_margin_router is not None
        assert snapshot_router is not None
