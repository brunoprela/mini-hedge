"""FastAPI routes for fund structures."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fund_structures.dependencies import get_fund_structures_service
from app.modules.fund_structures.interfaces import (
    BookRebalanceResult,
    FeederSubscription,
    FundOfFundsHolding,
    FundOfFundsNAV,
    MasterFeederLink,
    StrategyBook,
)
from app.modules.fund_structures.services import FundStructuresService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db, get_read_db

router = APIRouter(prefix="/fund-structures", tags=["fund-structures"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateMasterFeederRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    master_fund_slug: str
    feeder_fund_slug: str
    allocation_pct: Decimal


class CreateBookRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    fund_slug: str
    name: str
    level: str
    parent_id: UUID | None = None
    portfolio_id: UUID | None = None
    target_allocation_pct: Decimal = Decimal("1.0")


class UpdateBookRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str | None = None
    target_allocation_pct: Decimal | None = None


class RebalanceCheckRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    book_navs: dict[UUID, Decimal]


class AddFoFHoldingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    fof_fund_slug: str
    underlying_fund_name: str
    allocation_pct: Decimal
    underlying_fund_slug: str | None = None
    is_internal: bool = False


class UpdateHoldingNAVRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    nav: Decimal


# ---------------------------------------------------------------------------
# Master-Feeder routes
# ---------------------------------------------------------------------------


@router.post("/master-feeder", response_model=MasterFeederLink)
async def create_master_feeder_link(
    body: CreateMasterFeederRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_db),
) -> MasterFeederLink:
    return await service.create_master_feeder_link(
        body.master_fund_slug,
        body.feeder_fund_slug,
        body.allocation_pct,
        session=session,
    )


@router.get(
    "/master-feeder/{master_slug}",
    response_model=list[MasterFeederLink],
)
async def get_feeders_for_master(
    master_slug: str,
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[MasterFeederLink]:
    return await service.get_feeder_structure(master_slug, session=session)


@router.get(
    "/master-feeder/feeder/{feeder_slug}",
    response_model=FeederSubscription | MasterFeederLink | None,
)
async def get_feeder_master(
    feeder_slug: str,
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_read_db),
) -> MasterFeederLink | None:
    record = await service._mf_repo.get_master_for_feeder(
        feeder_slug,
        session=session,
    )
    if record is None:
        return None
    return MasterFeederLink(
        id=UUID(record.id),
        master_fund_slug=record.master_fund_slug,
        feeder_fund_slug=record.feeder_fund_slug,
        allocation_pct=record.allocation_pct,
        is_active=record.is_active,
        created_at=record.created_at,
    )


# ---------------------------------------------------------------------------
# Strategy Book routes
# ---------------------------------------------------------------------------


@router.post("/books", response_model=StrategyBook)
async def create_book(
    body: CreateBookRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_db),
) -> StrategyBook:
    return await service.create_book(
        body.fund_slug,
        body.name,
        body.level,
        parent_id=str(body.parent_id) if body.parent_id else None,
        portfolio_id=str(body.portfolio_id) if body.portfolio_id else None,
        target_pct=body.target_allocation_pct,
        session=session,
    )


@router.get("/books/{fund_slug}", response_model=list[StrategyBook])
async def get_book_tree(
    fund_slug: str,
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[StrategyBook]:
    return await service.get_book_tree(fund_slug, session=session)


@router.put("/books/{book_id}", response_model=StrategyBook | None)
async def update_book(
    book_id: UUID,
    body: UpdateBookRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_db),
) -> StrategyBook | None:
    record = await service._sb_repo.update(
        str(book_id),
        name=body.name,
        target_pct=body.target_allocation_pct,
        session=session,
    )
    if record is None:
        return None
    return service._to_strategy_book(record)


@router.delete("/books/{book_id}", status_code=204)
async def delete_book(
    book_id: UUID,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_db),
) -> None:
    await service._sb_repo.delete(str(book_id), session=session)


@router.post(
    "/books/{fund_slug}/rebalance-check",
    response_model=list[BookRebalanceResult],
)
async def check_rebalance(
    fund_slug: str,
    body: RebalanceCheckRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[BookRebalanceResult]:
    return await service.check_rebalance(
        fund_slug,
        body.book_navs,
        session=session,
    )


# ---------------------------------------------------------------------------
# Fund of Funds routes
# ---------------------------------------------------------------------------


@router.post("/fof/holdings", response_model=FundOfFundsHolding)
async def add_fof_holding(
    body: AddFoFHoldingRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_db),
) -> FundOfFundsHolding:
    return await service.add_fof_holding(
        body.fof_fund_slug,
        body.underlying_fund_name,
        body.allocation_pct,
        underlying_slug=body.underlying_fund_slug,
        is_internal=body.is_internal,
        session=session,
    )


@router.get(
    "/fof/{fof_slug}/holdings",
    response_model=list[FundOfFundsHolding],
)
async def list_fof_holdings(
    fof_slug: str,
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FundOfFundsHolding]:
    return await service.get_fof_holdings(fof_slug, session=session)


@router.get("/fof/{fof_slug}/nav", response_model=FundOfFundsNAV)
async def compute_fof_nav(
    fof_slug: str,
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_read_db),
) -> FundOfFundsNAV:
    return await service.compute_fof_nav(fof_slug, session=session)


@router.put("/fof/holdings/{holding_id}/nav", status_code=204)
async def update_holding_nav(
    holding_id: UUID,
    body: UpdateHoldingNAVRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: FundStructuresService = Depends(get_fund_structures_service),
    session: AsyncSession = Depends(get_db),
) -> None:
    await service.update_holding_nav(str(holding_id), body.nav, session=session)
