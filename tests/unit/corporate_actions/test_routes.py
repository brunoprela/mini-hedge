"""Unit tests for corporate actions routes — calls route functions directly with
mocked dependencies (no HTTP server needed)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.corporate_actions.routes.corporate_action import (
    list_corporate_actions,
    process_corporate_actions,
)


class TestListCorporateActions:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self):
        service = AsyncMock()
        service.list_processed = AsyncMock(return_value=[])
        session = AsyncMock()
        ctx = MagicMock()

        result = await list_corporate_actions(
            request_context=ctx,
            service=service,
            session=session,
        )

        assert result == []
        service.list_processed.assert_called_once_with(session=session)


class TestProcessCorporateActions:
    @pytest.mark.asyncio
    async def test_delegates_to_service(self):
        service = AsyncMock()
        service.fetch_and_process = AsyncMock(return_value=[])
        session = AsyncMock()
        ctx = MagicMock()
        ctx.fund_slug = "alpha"

        result = await process_corporate_actions(
            portfolio_id="p1",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            request_context=ctx,
            service=service,
            session=session,
        )

        assert result == []
        service.fetch_and_process.assert_called_once_with(
            fund_slug="alpha",
            portfolio_id="p1",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            session=session,
        )

    @pytest.mark.asyncio
    async def test_raises_400_when_no_fund_slug(self):
        from fastapi import HTTPException

        service = AsyncMock()
        session = AsyncMock()
        ctx = MagicMock()
        ctx.fund_slug = None

        with pytest.raises(HTTPException) as exc_info:
            await process_corporate_actions(
                portfolio_id="p1",
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                request_context=ctx,
                service=service,
                session=session,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_raises_400_when_fund_slug_empty_string(self):
        from fastapi import HTTPException

        service = AsyncMock()
        session = AsyncMock()
        ctx = MagicMock()
        ctx.fund_slug = ""

        with pytest.raises(HTTPException) as exc_info:
            await process_corporate_actions(
                portfolio_id="p1",
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                request_context=ctx,
                service=service,
                session=session,
            )

        assert exc_info.value.status_code == 400
