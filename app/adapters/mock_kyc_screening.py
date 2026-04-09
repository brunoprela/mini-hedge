"""Deterministic mock KYC/AML screening adapter.

Screening results are driven by the investor name:
- Names containing "BLOCKED" → sanctions hit, KYC rejected
- Names containing "PEP" → PEP flag set (still approved, requires manual review)
- Names containing "REJECT" → KYC rejected, AML flagged
- All others → fully approved, sanctions clear, source of funds verified
"""

from __future__ import annotations

from app.modules.investor_operations.interfaces import (
    AMLStatus,
    KYCScreeningResult,
    KYCStatus,
)


class MockKYCScreeningAdapter:
    """In-process mock that returns deterministic results based on name patterns."""

    async def screen_investor(
        self,
        *,
        investor_id: str,
        name: str,
        entity_type: str,
        tax_jurisdiction: str | None = None,
    ) -> KYCScreeningResult:
        upper = name.upper()

        if "BLOCKED" in upper:
            return KYCScreeningResult(
                approved=False,
                kyc_status=KYCStatus.REJECTED,
                aml_status=AMLStatus.BLOCKED,
                sanctions_clear=False,
                pep_flag=False,
                source_of_funds_verified=False,
                screening_provider="mock-kyc",
                notes=f"Sanctions hit for {name}",
            )

        if "REJECT" in upper:
            return KYCScreeningResult(
                approved=False,
                kyc_status=KYCStatus.REJECTED,
                aml_status=AMLStatus.FLAGGED,
                sanctions_clear=True,
                pep_flag=False,
                source_of_funds_verified=False,
                screening_provider="mock-kyc",
                notes=f"KYC rejected for {name}",
            )

        pep_flag = "PEP" in upper
        return KYCScreeningResult(
            approved=True,
            kyc_status=KYCStatus.APPROVED,
            aml_status=AMLStatus.CLEARED,
            sanctions_clear=True,
            pep_flag=pep_flag,
            source_of_funds_verified=True,
            screening_provider="mock-kyc",
            notes=f"PEP flag raised for {name}" if pep_flag else "",
        )
