"""KYC/AML screening types and adapter protocol.

These types live in app.shared so both app.adapters (implementations)
and app.modules.investor_operations (consumers) can import them
without creating a circular dependency.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class KYCStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AMLStatus(StrEnum):
    PENDING = "pending"
    CLEARED = "cleared"
    FLAGGED = "flagged"
    BLOCKED = "blocked"


class KYCScreeningResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved: bool
    kyc_status: KYCStatus
    aml_status: AMLStatus
    sanctions_clear: bool
    pep_flag: bool
    source_of_funds_verified: bool
    screening_provider: str
    notes: str = ""


class KYCScreeningAdapter(Protocol):
    """Vendor-agnostic KYC/AML screening interface.

    Implementations: mock-kyc, Onfido, ComplyAdvantage, Refinitiv World-Check.
    """

    async def screen_investor(
        self,
        *,
        investor_id: str,
        name: str,
        entity_type: str,
        tax_jurisdiction: str | None = None,
    ) -> KYCScreeningResult: ...
