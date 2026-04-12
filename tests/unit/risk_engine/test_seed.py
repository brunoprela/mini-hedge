"""Unit tests for risk engine seed data — _profile_for and seed_dev_data."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.risk_engine.seed import _profile_for, _RISK_PROFILES, seed_dev_data


# ---------------------------------------------------------------------------
# _profile_for — pure function
# ---------------------------------------------------------------------------


class TestProfileFor:
    def test_equity_ls_by_equity(self) -> None:
        assert _profile_for("Equity L/S Portfolio") == _RISK_PROFILES["Equity L/S"]

    def test_equity_ls_by_ls(self) -> None:
        assert _profile_for("My L/S Fund") == _RISK_PROFILES["Equity L/S"]

    def test_equity_ls_by_long(self) -> None:
        assert _profile_for("Long-Short Alpha") == _RISK_PROFILES["Equity L/S"]

    def test_global_macro(self) -> None:
        assert _profile_for("Global Macro Strategy") == _RISK_PROFILES["Global Macro"]

    def test_stat_arb(self) -> None:
        assert _profile_for("Stat Arb Fund") == _RISK_PROFILES["Stat Arb"]

    def test_arb_keyword(self) -> None:
        assert _profile_for("Arbitrage Portfolio") == _RISK_PROFILES["Stat Arb"]

    def test_neutral_keyword(self) -> None:
        assert _profile_for("Market Neutral") == _RISK_PROFILES["Stat Arb"]

    def test_default_fallback(self) -> None:
        assert _profile_for("Some Random Fund") == _RISK_PROFILES["default"]


# ---------------------------------------------------------------------------
# seed_dev_data — async, fully mocked
# ---------------------------------------------------------------------------


class TestSeedDevData:
    async def test_skips_when_services_not_available(self) -> None:
        app = MagicMock()
        app.state = MagicMock(spec=[])  # no attributes at all
        sf = MagicMock()

        # Should not raise
        await seed_dev_data(app, sf)

    async def test_skips_when_counterparty_service_missing(self) -> None:
        app = MagicMock()
        del app.state.counterparty_risk_service
        sf = MagicMock()

        await seed_dev_data(app, sf)

    async def test_seeds_counterparties_and_snapshots(self) -> None:
        # Setup mock counterparty repo
        cpty_repo = AsyncMock()
        cpty_repo.list_counterparties.return_value = []  # no existing
        cpty_repo.save_counterparty = AsyncMock()

        counterparty_service = MagicMock()
        counterparty_service._counterparty_repo = cpty_repo

        # Setup mock snapshot repo
        snapshot_repo = AsyncMock()
        snapshot_repo.get_latest_snapshot.return_value = None
        snapshot_repo.save_snapshot = AsyncMock()

        risk_service = MagicMock()
        risk_service._snapshot_repo = snapshot_repo

        # Setup fund/portfolio repos
        fund = MagicMock()
        fund.id = str(uuid4())
        fund.slug = "alpha"

        portfolio = MagicMock()
        portfolio.id = str(uuid4())
        portfolio.name = "Equity L/S Portfolio"

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [fund]

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund.return_value = [portfolio]

        app = MagicMock()
        app.state.counterparty_risk_service = counterparty_service
        app.state.risk_snapshot_service = risk_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        # Should have saved 4 counterparties
        assert cpty_repo.save_counterparty.call_count == 4
        # Should have saved 5 snapshots (5 days of history for 1 portfolio)
        assert snapshot_repo.save_snapshot.call_count == 5

    async def test_skips_existing_counterparties(self) -> None:
        from app.modules.risk_engine.seed import _COUNTERPARTIES

        # Pretend all counterparties already exist
        existing = [MagicMock(id=c.id) for c in _COUNTERPARTIES]
        cpty_repo = AsyncMock()
        cpty_repo.list_counterparties.return_value = existing
        cpty_repo.save_counterparty = AsyncMock()

        counterparty_service = MagicMock()
        counterparty_service._counterparty_repo = cpty_repo

        snapshot_repo = AsyncMock()
        snapshot_repo.get_latest_snapshot.return_value = MagicMock()  # existing snapshot

        risk_service = MagicMock()
        risk_service._snapshot_repo = snapshot_repo

        fund = MagicMock()
        fund.id = str(uuid4())
        fund.slug = "beta"

        portfolio = MagicMock()
        portfolio.id = str(uuid4())
        portfolio.name = "Global Macro"

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [fund]

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund.return_value = [portfolio]

        app = MagicMock()
        app.state.counterparty_risk_service = counterparty_service
        app.state.risk_snapshot_service = risk_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        # No new counterparties saved
        cpty_repo.save_counterparty.assert_not_called()
        # No new snapshots saved (existing snapshot found)
        snapshot_repo.save_snapshot.assert_not_called()
