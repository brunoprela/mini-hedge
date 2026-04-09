"""KYCScreeningAdapter protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.modules.investor_operations.interfaces import KYCScreeningResult


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
