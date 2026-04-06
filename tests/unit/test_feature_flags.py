"""Unit tests for the feature flag service."""

from __future__ import annotations

import pytest

from app.shared.feature_flags import FeatureFlagService


class TestFeatureFlagService:
    @pytest.mark.asyncio
    async def test_static_mode_returns_defaults(self) -> None:
        flags = FeatureFlagService(defaults={"new_compliance_rule": True})
        await flags.connect()

        assert await flags.is_enabled("new_compliance_rule") is True
        assert await flags.is_enabled("unknown_flag") is False

    @pytest.mark.asyncio
    async def test_default_parameter(self) -> None:
        flags = FeatureFlagService()
        await flags.connect()

        assert await flags.is_enabled("anything", default=True) is True
        assert await flags.is_enabled("anything", default=False) is False

    @pytest.mark.asyncio
    async def test_set_default(self) -> None:
        flags = FeatureFlagService()
        flags.set_default("kill_switch", True)

        assert await flags.is_enabled("kill_switch") is True

    @pytest.mark.asyncio
    async def test_get_value_returns_default(self) -> None:
        flags = FeatureFlagService()
        value = await flags.get_value("some_flag", default="v2")
        assert value == "v2"

    @pytest.mark.asyncio
    async def test_connect_without_config_uses_static(self) -> None:
        flags = FeatureFlagService(flagsmith_url="", flagsmith_key="")
        await flags.connect()
        assert flags._client is None
