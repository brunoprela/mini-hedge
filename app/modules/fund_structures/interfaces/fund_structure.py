"""Fund structures public interface — enums and DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FundStructureType(StrEnum):
    STANDALONE = "standalone"
    MASTER = "master"
    FEEDER = "feeder"
    FUND_OF_FUNDS = "fund_of_funds"


class BookLevel(StrEnum):
    FUND = "fund"
    STRATEGY = "strategy"
    SUB_STRATEGY = "sub_strategy"
    SLEEVE = "sleeve"


class AllocationMethod(StrEnum):
    PRO_RATA = "pro_rata"  # Proportional to NAV
    FIXED = "fixed"  # Fixed percentage
    EQUAL = "equal"  # Equal split


# ---------------------------------------------------------------------------
# DTOs (Pydantic, frozen)
# ---------------------------------------------------------------------------


class MasterFeederLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    master_fund_slug: str
    feeder_fund_slug: str
    allocation_pct: Decimal  # feeder's share of master
    is_active: bool
    created_at: datetime


class StrategyBook(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    fund_slug: str
    name: str
    level: BookLevel
    parent_id: UUID | None  # null for top-level
    portfolio_id: UUID | None  # linked portfolio
    target_allocation_pct: Decimal
    actual_allocation_pct: Decimal | None
    is_active: bool


class FundOfFundsHolding(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    fof_fund_slug: str
    underlying_fund_slug: str | None  # internal fund
    underlying_fund_name: str  # display name (for external too)
    allocation_pct: Decimal
    current_nav: Decimal
    is_internal: bool  # true if underlying is on this platform


class FeederSubscription(BaseModel):
    model_config = ConfigDict(frozen=True)

    feeder_fund_slug: str
    amount: Decimal
    allocated_to_master: Decimal


class BookRebalanceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    book_id: UUID
    book_name: str
    target_pct: Decimal
    current_pct: Decimal
    drift_pct: Decimal
    suggested_trade_amount: Decimal


class FundOfFundsNAV(BaseModel):
    model_config = ConfigDict(frozen=True)

    fof_fund_slug: str
    total_nav: Decimal
    holdings: list[FundOfFundsHolding]
    computed_at: datetime
