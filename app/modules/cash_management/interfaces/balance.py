"""Cash balance DTOs and reader protocol."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.modules.cash_management.interfaces.settlement import CashProjection, SettlementRecord


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


class CashReader(Protocol):
    """Public read interface for other modules."""

    async def get_balances(self, portfolio_id: UUID) -> list[CashBalance]: ...

    async def get_pending_settlements(self, portfolio_id: UUID) -> list[SettlementRecord]: ...

    async def get_projection(
        self,
        portfolio_id: UUID,
        horizon_days: int,
    ) -> CashProjection: ...
