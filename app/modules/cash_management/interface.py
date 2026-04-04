"""Cash management public interface — Protocol + value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SettlementStatus(StrEnum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CashFlowType(StrEnum):
    TRADE_SETTLEMENT = "trade_settlement"
    DIVIDEND = "dividend"
    FEE = "fee"
    SUBSCRIPTION = "subscription"
    REDEMPTION = "redemption"
    INTEREST = "interest"
    TRANSFER = "transfer"


class JournalEntryType(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"


# ---------------------------------------------------------------------------
# Settlement conventions by country
# ---------------------------------------------------------------------------

# T+N settlement cycles (business days after trade date)
SETTLEMENT_CONVENTIONS: dict[str, int] = {
    "US": 1,  # T+1 (SEC rule change 2024)
    "CA": 1,  # T+1
    "GB": 1,  # T+1
    "DE": 2,  # T+2
    "FR": 2,  # T+2
    "CH": 2,  # T+2
    "JP": 2,  # T+2
    "KR": 2,  # T+2
    "AU": 2,  # T+2
}

DEFAULT_SETTLEMENT_DAYS = 2  # T+2 fallback


# ---------------------------------------------------------------------------
# Internal value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SettlementLadderEntry:
    """A single row in the settlement ladder."""

    settlement_date: date
    currency: str
    expected_inflow: Decimal
    expected_outflow: Decimal
    net_flow: Decimal
    cumulative_balance: Decimal


@dataclass(frozen=True)
class CashProjectionEntry:
    """Forward-looking cash projection entry."""

    projection_date: date
    currency: str
    opening_balance: Decimal
    inflows: Decimal
    outflows: Decimal
    closing_balance: Decimal
    flow_details: list[dict[str, str]]


# ---------------------------------------------------------------------------
# API / read-model value objects (Pydantic)
# ---------------------------------------------------------------------------


class CashBalance(BaseModel):
    """Current cash balance for a portfolio in a currency."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    currency: str
    available_balance: Decimal
    pending_inflows: Decimal
    pending_outflows: Decimal
    total_balance: Decimal
    updated_at: datetime


class SettlementRecord(BaseModel):
    """A trade settlement entry."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    order_id: UUID | None = None
    instrument_id: str
    currency: str
    settlement_amount: Decimal
    settlement_date: date
    trade_date: date
    status: SettlementStatus
    created_at: datetime


class CashProjection(BaseModel):
    """Cash projection summary for a portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    base_currency: str
    horizon_days: int
    entries: list[CashProjectionEntry] = []
    projected_at: datetime


class SettlementLadder(BaseModel):
    """Settlement ladder view."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    entries: list[SettlementLadderEntry] = []
    generated_at: datetime


# ---------------------------------------------------------------------------
# Module protocol
# ---------------------------------------------------------------------------


class CashReader(Protocol):
    """Public read interface for other modules."""

    async def get_balances(self, portfolio_id: UUID) -> list[CashBalance]: ...

    async def get_pending_settlements(self, portfolio_id: UUID) -> list[SettlementRecord]: ...

    async def get_projection(
        self,
        portfolio_id: UUID,
        horizon_days: int,
    ) -> CashProjection: ...
