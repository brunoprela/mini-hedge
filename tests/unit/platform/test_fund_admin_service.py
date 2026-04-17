"""Unit tests for FundAdminService — fund lifecycle and provisioning."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.services.fund import FundAdminService
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import NotFoundError, ValidationError


def _make_request_context() -> RequestContext:
    return RequestContext(actor_id="op-1", actor_type=ActorType.OPERATOR)


def _make_fund_record(
    fund_id: str = "fund-1",
    slug: str = "alpha-fund",
    name: str = "Alpha Fund",
    status: str = "active",
    base_currency: str = "USD",
) -> MagicMock:
    r = MagicMock()
    r.id = fund_id
    r.slug = slug
    r.name = name
    r.status = status
    r.base_currency = base_currency
    return r


def _make_service(
    existing_fund: MagicMock | None = None,
    with_engine: bool = False,
    with_event_bus: bool = False,
) -> tuple[FundAdminService, AsyncMock, AsyncMock, AsyncMock]:
    fund_repo = AsyncMock()
    fund_repo.list_paginated = AsyncMock(return_value=([], 0))
    fund_repo.get_by_slug = AsyncMock(return_value=existing_fund)

    async def _insert_with_id(record, **kw):
        if not record.id:
            record.id = "generated-id"

    fund_repo.insert = AsyncMock(side_effect=_insert_with_id)
    fund_repo.update = AsyncMock(return_value=None)

    fga_client = AsyncMock()
    audit_repo = AsyncMock()
    audit_repo.insert_admin_event = AsyncMock()

    engine = AsyncMock() if with_engine else None
    event_bus = AsyncMock() if with_event_bus else None

    svc = FundAdminService(
        fund_repo=fund_repo,
        fga_client=fga_client,
        audit_repo=audit_repo,
        engine=engine,
        event_bus=event_bus,
    )
    return svc, fund_repo, fga_client, audit_repo


class TestListFunds:
    @pytest.mark.asyncio
    async def test_returns_paginated_funds(self) -> None:
        svc, fund_repo, _, _ = _make_service()
        records = [_make_fund_record("f1", "fund-a", "Fund A"), _make_fund_record("f2", "fund-b", "Fund B")]
        fund_repo.list_paginated = AsyncMock(return_value=(records, 2))

        result = await svc.list_funds(limit=10, offset=0)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].slug == "fund-a"
        assert result.items[1].slug == "fund-b"
        assert result.limit == 10

    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        svc, _, _, _ = _make_service()

        result = await svc.list_funds()

        assert result.total == 0
        assert result.items == []


class TestCreateFund:
    @pytest.mark.asyncio
    async def test_creates_and_audits(self) -> None:
        svc, fund_repo, _, audit_repo = _make_service()
        ctx = _make_request_context()

        result = await svc.create_fund(
            slug="new-fund", name="New Fund", base_currency="USD", request_context=ctx,
        )

        assert result.slug == "new-fund"
        assert result.name == "New Fund"
        fund_repo.insert.assert_called_once()
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_slug_raises(self) -> None:
        existing = _make_fund_record(slug="taken")
        svc, _, _, _ = _make_service(existing_fund=existing)
        ctx = _make_request_context()

        with pytest.raises(ValidationError, match="slug already in use"):
            await svc.create_fund(
                slug="taken", name="Dup", base_currency="USD", request_context=ctx,
            )

    @pytest.mark.asyncio
    async def test_calls_on_fund_created_hooks(self) -> None:
        svc, _, _, _ = _make_service()
        hook = AsyncMock()
        svc.register_on_fund_created(hook)
        ctx = _make_request_context()

        await svc.create_fund(
            slug="hooked-fund", name="H", base_currency="EUR", request_context=ctx,
        )

        hook.assert_called_once_with("hooked-fund")

    @pytest.mark.asyncio
    async def test_hook_failure_does_not_abort(self) -> None:
        svc, fund_repo, _, audit_repo = _make_service()
        bad_hook = AsyncMock(side_effect=RuntimeError("boom"))
        svc.register_on_fund_created(bad_hook)
        ctx = _make_request_context()

        # Should not raise — hook failures are logged but swallowed
        result = await svc.create_fund(
            slug="safe-fund", name="S", base_currency="USD", request_context=ctx,
        )

        assert result.slug == "safe-fund"
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_provisions_schema_and_topics(self) -> None:
        svc, _, _, _ = _make_service(with_engine=True, with_event_bus=True)
        ctx = _make_request_context()

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            schema_mock = AsyncMock()
            topics_mock = AsyncMock()
            mp.setattr("app.modules.platform.services.fund.create_fund_schema", schema_mock)
            mp.setattr("app.modules.platform.services.fund.create_fund_kafka_topics", topics_mock)

            await svc.create_fund(
                slug="infra-fund", name="I", base_currency="GBP", request_context=ctx,
            )

            schema_mock.assert_called_once()
            topics_mock.assert_called_once()


class TestUpdateFund:
    @pytest.mark.asyncio
    async def test_updates_and_audits(self) -> None:
        updated = _make_fund_record("f1", "alpha", "Alpha Updated")
        svc, fund_repo, _, audit_repo = _make_service()
        fund_repo.update = AsyncMock(return_value=updated)
        ctx = _make_request_context()

        from app.modules.platform.interfaces.fund import UpdateFundRequest

        result = await svc.update_fund("f1", UpdateFundRequest(name="Alpha Updated"), request_context=ctx)

        assert result.name == "Alpha Updated"
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc, fund_repo, _, _ = _make_service()
        fund_repo.update = AsyncMock(return_value=None)
        ctx = _make_request_context()

        from app.modules.platform.interfaces.fund import UpdateFundRequest

        with pytest.raises(NotFoundError):
            await svc.update_fund("missing", UpdateFundRequest(name="X"), request_context=ctx)
