"""Unit tests for CounterpartyRiskService — exposures and credit risk."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.risk_engine.services.counterparty import CounterpartyRiskService

_PORT_ID = uuid4()
_CPTY_ID = str(uuid4())


def _make_cpty_record(
    name: str = "Goldman Sachs",
    cpty_type: str = "prime_broker",
    credit_limit: Decimal = Decimal("50000000"),
) -> MagicMock:
    r = MagicMock()
    r.id = _CPTY_ID
    r.name = name
    r.counterparty_type = cpty_type
    r.credit_rating = "A+"
    r.credit_limit = credit_limit
    r.netting_eligible = True
    r.is_active = True
    return r


def _make_exposure_record(
    gross: Decimal = Decimal("10000000"),
    net: Decimal = Decimal("8000000"),
) -> MagicMock:
    r = MagicMock()
    r.counterparty_id = _CPTY_ID
    r.portfolio_id = str(_PORT_ID)
    r.business_date = datetime.now(timezone.utc)
    r.gross_exposure = gross
    r.net_exposure = net
    r.collateral_held = Decimal("1000000")
    r.collateral_posted = Decimal("500000")
    r.credit_limit = Decimal("50000000")
    r.utilization_pct = Decimal("0.16")
    r.breach = False
    return r


def _make_service() -> tuple[CounterpartyRiskService, AsyncMock, AsyncMock]:
    cpty_repo = AsyncMock()
    cpty_repo.list_counterparties = AsyncMock(return_value=[])
    cpty_repo.get_counterparty = AsyncMock(return_value=None)
    cpty_repo.get_counterparty_map = AsyncMock(return_value={})
    cpty_repo.save_counterparty = AsyncMock()

    exposure_repo = AsyncMock()
    exposure_repo.get_counterparty_exposures = AsyncMock(return_value=[])
    exposure_repo.save_counterparty_exposure = AsyncMock()

    svc = CounterpartyRiskService(
        counterparty_repo=cpty_repo,
        counterparty_exposure_repo=exposure_repo,
    )
    return svc, cpty_repo, exposure_repo


class TestListCounterparties:
    @pytest.mark.asyncio
    async def test_returns_counterparty_list(self) -> None:
        svc, cpty_repo, _ = _make_service()
        cpty_repo.list_counterparties = AsyncMock(return_value=[_make_cpty_record()])

        result = await svc.list_counterparties()

        assert len(result) == 1
        assert result[0].name == "Goldman Sachs"
        assert result[0].credit_limit == Decimal("50000000")

    @pytest.mark.asyncio
    async def test_empty_counterparties(self) -> None:
        svc, _, _ = _make_service()

        result = await svc.list_counterparties()

        assert result == []


class TestGetCounterpartyExposures:
    @pytest.mark.asyncio
    async def test_returns_exposures_with_names(self) -> None:
        svc, cpty_repo, exposure_repo = _make_service()
        exposure_repo.get_counterparty_exposures = AsyncMock(
            return_value=[_make_exposure_record()]
        )
        cpty_repo.get_counterparty_map = AsyncMock(
            return_value={_CPTY_ID: "Goldman Sachs"}
        )

        result = await svc.get_counterparty_exposures(_PORT_ID)

        assert len(result) == 1
        assert result[0].counterparty_name == "Goldman Sachs"
        assert result[0].gross_exposure == Decimal("10000000")

    @pytest.mark.asyncio
    async def test_unknown_counterparty_gets_unknown_name(self) -> None:
        svc, cpty_repo, exposure_repo = _make_service()
        exposure_repo.get_counterparty_exposures = AsyncMock(
            return_value=[_make_exposure_record()]
        )
        cpty_repo.get_counterparty_map = AsyncMock(return_value={})

        result = await svc.get_counterparty_exposures(_PORT_ID)

        assert result[0].counterparty_name == "Unknown"

    @pytest.mark.asyncio
    async def test_empty_exposures(self) -> None:
        svc, _, _ = _make_service()

        result = await svc.get_counterparty_exposures(_PORT_ID)

        assert result == []


class TestRecordCounterpartyExposure:
    @pytest.mark.asyncio
    async def test_records_with_utilization(self) -> None:
        svc, cpty_repo, exposure_repo = _make_service()
        cpty_record = _make_cpty_record(credit_limit=Decimal("50000000"))
        cpty_repo.get_counterparty = AsyncMock(return_value=cpty_record)

        await svc.record_counterparty_exposure(
            counterparty_id=_CPTY_ID,
            portfolio_id=_PORT_ID,
            business_date=datetime.now(timezone.utc),
            gross_exposure=Decimal("10000000"),
            net_exposure=Decimal("8000000"),
        )

        exposure_repo.save_counterparty_exposure.assert_called_once()
        saved = exposure_repo.save_counterparty_exposure.call_args.args[0]
        assert saved.gross_exposure == Decimal("10000000")
        assert saved.breach is False

    @pytest.mark.asyncio
    async def test_detects_limit_breach(self) -> None:
        svc, cpty_repo, exposure_repo = _make_service()
        cpty_record = _make_cpty_record(credit_limit=Decimal("5000000"))
        cpty_repo.get_counterparty = AsyncMock(return_value=cpty_record)

        await svc.record_counterparty_exposure(
            counterparty_id=_CPTY_ID,
            portfolio_id=_PORT_ID,
            business_date=datetime.now(timezone.utc),
            gross_exposure=Decimal("10000000"),
            net_exposure=Decimal("8000000"),
        )

        saved = exposure_repo.save_counterparty_exposure.call_args.args[0]
        assert saved.breach is True

    @pytest.mark.asyncio
    async def test_unknown_counterparty_zero_limit(self) -> None:
        svc, cpty_repo, exposure_repo = _make_service()
        cpty_repo.get_counterparty = AsyncMock(return_value=None)

        await svc.record_counterparty_exposure(
            counterparty_id=_CPTY_ID,
            portfolio_id=_PORT_ID,
            business_date=datetime.now(timezone.utc),
            gross_exposure=Decimal("1000000"),
            net_exposure=Decimal("500000"),
        )

        saved = exposure_repo.save_counterparty_exposure.call_args.args[0]
        assert saved.credit_limit == Decimal(0)
        # No breach when limit is 0 (no limit set)
        assert saved.breach is False

    @pytest.mark.asyncio
    async def test_includes_collateral(self) -> None:
        svc, cpty_repo, exposure_repo = _make_service()
        cpty_repo.get_counterparty = AsyncMock(return_value=_make_cpty_record())

        await svc.record_counterparty_exposure(
            counterparty_id=_CPTY_ID,
            portfolio_id=_PORT_ID,
            business_date=datetime.now(timezone.utc),
            gross_exposure=Decimal("10000000"),
            net_exposure=Decimal("8000000"),
            collateral_held=Decimal("2000000"),
            collateral_posted=Decimal("1000000"),
        )

        saved = exposure_repo.save_counterparty_exposure.call_args.args[0]
        assert saved.collateral_held == Decimal("2000000")
        assert saved.collateral_posted == Decimal("1000000")
