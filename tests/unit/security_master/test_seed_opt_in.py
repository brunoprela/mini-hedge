"""Unit tests for opt-in instrument seeding."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSeedOptIn:
    """Verify instrument seeding respects seed_on_startup config."""

    @pytest.mark.asyncio
    async def test_seeding_skipped_when_disabled(self) -> None:
        from app.modules.security_master.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        settings = MagicMock()
        settings.seed_on_startup = False

        with patch("app.modules.security_master.wiring._is_local_env", return_value=True), \
             patch("app.modules.security_master.wiring._seed_instruments") as mock_seed, \
             patch("app.modules.security_master.wiring.InstrumentRepository"), \
             patch("app.modules.security_master.wiring.IdentifierRepository"), \
             patch("app.modules.security_master.wiring.SecurityMasterService"):
            await setup(app, sf, settings=settings)

        mock_seed.assert_not_called()

    @pytest.mark.asyncio
    async def test_seeding_runs_when_enabled(self) -> None:
        from app.modules.security_master.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        settings = MagicMock()
        settings.seed_on_startup = True

        with patch("app.modules.security_master.wiring._is_local_env", return_value=True), \
             patch("app.modules.security_master.wiring._seed_instruments", new_callable=AsyncMock) as mock_seed, \
             patch("app.modules.security_master.wiring.InstrumentRepository"), \
             patch("app.modules.security_master.wiring.IdentifierRepository"), \
             patch("app.modules.security_master.wiring.SecurityMasterService"):
            await setup(app, sf, settings=settings)

        mock_seed.assert_called_once()

    @pytest.mark.asyncio
    async def test_seeding_defaults_to_enabled(self) -> None:
        from app.modules.security_master.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        # No settings passed — should default to seed_on_startup=True

        with patch("app.modules.security_master.wiring._is_local_env", return_value=True), \
             patch("app.modules.security_master.wiring._seed_instruments", new_callable=AsyncMock) as mock_seed, \
             patch("app.modules.security_master.wiring.InstrumentRepository"), \
             patch("app.modules.security_master.wiring.IdentifierRepository"), \
             patch("app.modules.security_master.wiring.SecurityMasterService"):
            await setup(app, sf, settings=None)

        mock_seed.assert_called_once()

    @pytest.mark.asyncio
    async def test_seeding_skipped_in_non_local_env(self) -> None:
        from app.modules.security_master.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        settings = MagicMock()
        settings.seed_on_startup = True

        with patch("app.modules.security_master.wiring._is_local_env", return_value=False), \
             patch("app.modules.security_master.wiring._seed_instruments") as mock_seed, \
             patch("app.modules.security_master.wiring.InstrumentRepository"), \
             patch("app.modules.security_master.wiring.IdentifierRepository"), \
             patch("app.modules.security_master.wiring.SecurityMasterService"):
            await setup(app, sf, settings=settings)

        mock_seed.assert_not_called()
