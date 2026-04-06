"""Feature flag service — dynamic toggles without redeployment.

Wraps a Flagsmith (or compatible) backend for feature flag evaluation.
Falls back to a static in-memory dict when no external service is configured.

Usage in application code::

    if await flags.is_enabled("new_compliance_rule", default=False):
        # New behavior
    else:
        # Old behavior

Critical for:
  - Gradual rollout of new compliance rules
  - Kill switches for trading strategies
  - A/B testing alpha signal changes
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class FeatureFlagService:
    """Feature flag evaluation with optional Flagsmith backend."""

    def __init__(
        self,
        *,
        flagsmith_url: str = "",
        flagsmith_key: str = "",
        defaults: dict[str, bool] | None = None,
    ) -> None:
        self._flagsmith_url = flagsmith_url
        self._flagsmith_key = flagsmith_key
        self._defaults = defaults or {}
        self._client: Any | None = None

    async def connect(self) -> None:
        """Initialize Flagsmith client if configured."""
        if not self._flagsmith_url or not self._flagsmith_key:
            logger.info("feature_flags_static_mode", flags=list(self._defaults.keys()))
            return

        try:
            from flagsmith import Flagsmith

            self._client = Flagsmith(
                environment_key=self._flagsmith_key,
                api_url=self._flagsmith_url,
            )
            logger.info("feature_flags_connected", url=self._flagsmith_url)
        except ImportError:
            logger.warning("feature_flags_flagsmith_not_installed")
        except Exception:
            logger.warning("feature_flags_connection_failed", exc_info=True)

    async def is_enabled(self, flag_name: str, *, default: bool = False) -> bool:
        """Check if a feature flag is enabled."""
        if self._client is not None:
            try:
                flags = self._client.get_environment_flags()
                return flags.is_feature_enabled(flag_name)
            except Exception:
                logger.warning("feature_flag_eval_failed", flag=flag_name)

        return self._defaults.get(flag_name, default)

    async def get_value(self, flag_name: str, *, default: str = "") -> str:
        """Get the value of a feature flag (for multivariate flags)."""
        if self._client is not None:
            try:
                flags = self._client.get_environment_flags()
                return flags.get_feature_value(flag_name) or default
            except Exception:
                logger.warning("feature_flag_value_failed", flag=flag_name)

        return default

    def set_default(self, flag_name: str, enabled: bool) -> None:
        """Set a static default for local dev / testing."""
        self._defaults[flag_name] = enabled
