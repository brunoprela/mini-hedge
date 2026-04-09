"""Counterparty and credit risk DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CounterpartyType(StrEnum):
    BROKER = "broker"
    PRIME_BROKER = "prime_broker"
    CUSTODIAN = "custodian"
    OTC_COUNTERPARTY = "otc_counterparty"


@dataclass(frozen=True)
class CounterpartyInfo:
    id: UUID
    name: str
    counterparty_type: CounterpartyType
    credit_rating: str | None
    credit_limit: Decimal
    netting_eligible: bool
    is_active: bool


class CounterpartyExposure(BaseModel):
    model_config = ConfigDict(frozen=True)

    counterparty_id: UUID
    counterparty_name: str
    portfolio_id: UUID
    business_date: datetime
    gross_exposure: Decimal
    net_exposure: Decimal
    collateral_held: Decimal
    collateral_posted: Decimal
    credit_limit: Decimal
    utilization_pct: Decimal
    breach: bool
