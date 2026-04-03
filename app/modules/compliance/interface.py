"""Compliance module public interface — Protocol + value objects.

Other modules depend ONLY on this file, never on internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RuleType(StrEnum):
    CONCENTRATION_LIMIT = "concentration_limit"
    SECTOR_LIMIT = "sector_limit"
    COUNTRY_LIMIT = "country_limit"
    RESTRICTED_LIST = "restricted_list"
    SHORT_SELLING = "short_selling"


class Severity(StrEnum):
    BLOCK = "block"
    WARNING = "warning"
    BREACH = "breach"


# ---------------------------------------------------------------------------
# Internal domain value objects (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationResult:
    """Outcome of evaluating a single compliance rule."""

    rule_id: UUID
    rule_name: str
    passed: bool
    severity: Severity
    message: str
    current_value: Decimal | None = None
    limit_value: Decimal | None = None


# ---------------------------------------------------------------------------
# API / read-model value objects (Pydantic — serialization boundary)
# ---------------------------------------------------------------------------


class RuleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    rule_type: RuleType
    severity: Severity
    parameters: dict[str, object]
    is_active: bool
    created_at: datetime


class TradeCheckRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    instrument_id: str
    side: str
    quantity: Decimal
    price: Decimal


class ComplianceDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved: bool
    results: list[EvaluationResult]
    blocked_by: list[str]


class Violation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    rule_id: UUID
    rule_name: str
    severity: Severity
    message: str
    current_value: Decimal | None
    limit_value: Decimal | None
    detected_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


# ---------------------------------------------------------------------------
# Module protocol — the public interface for other modules
# ---------------------------------------------------------------------------


class ComplianceChecker(Protocol):
    """Pre-trade compliance check interface."""

    async def check_trade(
        self,
        request: TradeCheckRequest,
    ) -> ComplianceDecision: ...
