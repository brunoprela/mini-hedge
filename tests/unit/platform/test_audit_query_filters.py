"""Unit tests for audit log query filters (actor_id, entity_type, entity_id, correlation_id)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.services.access import AccessGrantService


class TestAuditQueryFilters:
    """Verify all filter parameters flow from AccessGrantService to the repo query."""

    def _make_service(self):
        audit_repo = AsyncMock()
        audit_repo.query = AsyncMock(return_value=([], 0))
        service = AccessGrantService.__new__(AccessGrantService)
        service._audit_repo = audit_repo
        return service, audit_repo

    @pytest.mark.asyncio
    async def test_actor_id_passed_to_repo(self) -> None:
        service, repo = self._make_service()
        await service.list_audit(actor_id="user-123")
        repo.query.assert_called_once()
        assert repo.query.call_args.kwargs["actor_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_entity_type_passed_to_repo(self) -> None:
        service, repo = self._make_service()
        await service.list_audit(entity_type="order")
        repo.query.assert_called_once()
        assert repo.query.call_args.kwargs["entity_type"] == "order"

    @pytest.mark.asyncio
    async def test_entity_id_passed_to_repo(self) -> None:
        service, repo = self._make_service()
        await service.list_audit(entity_id="abc-123")
        repo.query.assert_called_once()
        assert repo.query.call_args.kwargs["entity_id"] == "abc-123"

    @pytest.mark.asyncio
    async def test_correlation_id_passed_to_repo(self) -> None:
        service, repo = self._make_service()
        await service.list_audit(correlation_id="corr-456")
        repo.query.assert_called_once()
        assert repo.query.call_args.kwargs["correlation_id"] == "corr-456"

    @pytest.mark.asyncio
    async def test_all_filters_combined(self) -> None:
        service, repo = self._make_service()
        await service.list_audit(
            fund_slug="alpha",
            event_type="order.created",
            actor_id="user-1",
            entity_type="order",
            entity_id="ord-1",
            correlation_id="corr-1",
        )
        repo.query.assert_called_once()
        kwargs = repo.query.call_args.kwargs
        assert kwargs["fund_slug"] == "alpha"
        assert kwargs["event_type"] == "order.created"
        assert kwargs["actor_id"] == "user-1"
        assert kwargs["entity_type"] == "order"
        assert kwargs["entity_id"] == "ord-1"
        assert kwargs["correlation_id"] == "corr-1"

    @pytest.mark.asyncio
    async def test_none_filters_passed_by_default(self) -> None:
        service, repo = self._make_service()
        await service.list_audit()
        kwargs = repo.query.call_args.kwargs
        assert kwargs["actor_id"] is None
        assert kwargs["entity_type"] is None
        assert kwargs["entity_id"] is None
        assert kwargs["correlation_id"] is None
