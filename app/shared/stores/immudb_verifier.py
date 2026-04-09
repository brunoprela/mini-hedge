"""Integrity verification — compares PostgreSQL audit records against immudb.

Reads a batch of audit entries from PostgreSQL and verifies each one
exists in immudb with a matching payload.  Any mismatch proves the
PostgreSQL record was tampered with after ingestion.

Designed to run as a periodic job (e.g. via Temporal or a manual API call).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.modules.platform.repositories import AuditLogRepository
    from app.shared.stores.immudb_client import ImmudbClient

logger = structlog.get_logger()


@dataclass
class VerificationResult:
    """Summary of an integrity verification run."""

    total_checked: int = 0
    verified: int = 0
    mismatches: list[str] = field(default_factory=list)
    missing_in_immudb: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.mismatches and not self.missing_in_immudb


async def verify_audit_batch(
    *,
    audit_repo: AuditLogRepository,
    immudb_client: ImmudbClient,
    fund_slug: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> VerificationResult:
    """Verify a batch of PostgreSQL audit entries against immudb.

    Returns a :class:`VerificationResult` summarizing any discrepancies.
    """
    result = VerificationResult()

    records, _total = await audit_repo.query(
        fund_slug=fund_slug,
        limit=limit,
        offset=offset,
    )

    for record in records:
        result.total_checked += 1
        event_id = record.event_id

        immudb_entry = await immudb_client.verified_get(f"audit:{event_id}")

        if immudb_entry is None:
            result.missing_in_immudb.append(event_id)
            logger.warning("immudb_verification_missing", event_id=event_id)
            continue

        # Compare the payload — PostgreSQL stores it as JSONB, immudb as JSON string
        pg_payload = json.dumps(record.payload, default=str, sort_keys=True)
        immudb_payload = json.dumps(immudb_entry.get("data", {}), default=str, sort_keys=True)

        if pg_payload == immudb_payload:
            result.verified += 1
        else:
            result.mismatches.append(event_id)
            logger.error(
                "immudb_verification_mismatch",
                event_id=event_id,
                hint="PostgreSQL record differs from immudb witness",
            )

    logger.info(
        "immudb_verification_complete",
        total=result.total_checked,
        verified=result.verified,
        mismatches=len(result.mismatches),
        missing=len(result.missing_in_immudb),
    )

    return result
