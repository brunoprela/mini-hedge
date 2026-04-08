"""Capital accounts public interface — DTOs, enums, protocols."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InvestorEntityType(StrEnum):
    INDIVIDUAL = "individual"
    INSTITUTION = "institution"
    FUND_OF_FUNDS = "fund_of_funds"


class TransactionType(StrEnum):
    SUBSCRIPTION = "subscription"
    REDEMPTION = "redemption"
    PNL_ALLOCATION = "pnl_allocation"
    MGMT_FEE_ALLOCATION = "mgmt_fee_allocation"
    PERF_FEE_ALLOCATION = "perf_fee_allocation"
    PERIOD_CLOSE = "period_close"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class InvestorInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    entity_type: InvestorEntityType
    tax_jurisdiction: str | None = None
    contact_email: str | None = None
    is_active: bool


class CapitalAccountSummary(BaseModel):
    """Current state of an investor's capital in a fund."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    investor_id: UUID
    investor_name: str
    share_class: str
    beginning_capital: Decimal
    contributions: Decimal
    withdrawals: Decimal
    pnl_allocation: Decimal
    management_fee_allocation: Decimal
    performance_fee_allocation: Decimal
    ending_capital: Decimal
    ownership_pct: Decimal
    shares_held: Decimal
    effective_date: date


class CapitalTransaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    capital_account_id: UUID
    transaction_type: TransactionType
    amount: Decimal
    shares: Decimal
    nav_per_share: Decimal
    business_date: date
    notes: str | None = None
    created_at: datetime


class FundCapitalOverview(BaseModel):
    """Aggregate capital metrics for a fund."""

    model_config = ConfigDict(frozen=True)

    total_aum: Decimal
    total_investors: int
    total_shares_outstanding: Decimal
    largest_investor_pct: Decimal
    last_allocation_date: date | None = None


class ShareClassSummary(BaseModel):
    """Per-class aggregate metrics."""

    model_config = ConfigDict(frozen=True)

    share_class: str
    total_aum: Decimal
    total_shares: Decimal
    nav_per_share: Decimal
    investor_count: int


# ---------------------------------------------------------------------------
# Calculator inputs/outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllocationInput:
    """Input for P&L and fee allocation across investors."""

    account_id: str
    ending_capital: Decimal
    ownership_pct: Decimal
    shares_held: Decimal


@dataclass(frozen=True)
class AllocationResult:
    """Result of allocating P&L or fees to a single investor."""

    account_id: str
    allocated_amount: Decimal
    new_ending_capital: Decimal
    new_ownership_pct: Decimal
