"""Unit tests for trade seeding via order flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSeedOrderFlowMode:
    """Verify seed_trades.py uses the order-flow path."""

    def test_order_flow_function_exists(self) -> None:
        import app.seed_trades as m

        assert hasattr(m, "_seed_via_order_flow")

    def test_all_trades_list_exists(self) -> None:
        from app.seed_trades import ALL_TRADES

        assert len(ALL_TRADES) > 0
        # Each trade is a 6-tuple
        for trade in ALL_TRADES[:5]:
            assert len(trade) == 6

    def test_fund_slug_mappings_cover_all_trades(self) -> None:
        from app.seed_trades import ALL_TRADES, FUND_SLUG_TO_ID, FUND_SLUG_TO_ACTOR

        slugs = {t[0] for t in ALL_TRADES}
        for slug in slugs:
            assert slug in FUND_SLUG_TO_ID, f"Missing fund ID for slug: {slug}"
            assert slug in FUND_SLUG_TO_ACTOR, f"Missing actor for slug: {slug}"
