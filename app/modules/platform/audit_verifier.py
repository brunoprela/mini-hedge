"""Integrity verification for the audit log hash chain."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.modules.platform.audit_repository import _compute_hash
from app.modules.platform.models import AuditLogRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


@dataclass(frozen=True)
class AuditVerificationResult:
    """Outcome of a hash-chain integrity check."""

    is_valid: bool
    records_checked: int
    first_broken_link: str | None = None


class AuditIntegrityVerifier(BaseRepository):
    """Walks the audit hash chain and verifies every link."""

    async def verify(
        self,
        *,
        limit: int = 10000,
        session: AsyncSession | None = None,
    ) -> AuditVerificationResult:
        """Verify the integrity of the audit log hash chain.

        Records are walked in chronological order (``created_at ASC``).
        For each record the expected hash is recomputed from the stored
        payload and the previous entry's hash; a mismatch indicates
        tampering.
        """
        async with self._session(session) as session:
            stmt = select(AuditLogRecord).order_by(AuditLogRecord.created_at.asc()).limit(limit)
            result = await session.execute(stmt)
            records = list(result.scalars().all())

            if not records:
                return AuditVerificationResult(is_valid=True, records_checked=0)

            prev_hash = ""
            for record in records:
                payload_str = json.dumps(record.payload, sort_keys=True)
                expected_hash = _compute_hash(payload_str, prev_hash)

                if record.entry_hash != expected_hash:
                    logger.warning(
                        "audit_hash_chain_broken",
                        event_id=record.event_id,
                        expected=expected_hash,
                        actual=record.entry_hash,
                    )
                    return AuditVerificationResult(
                        is_valid=False,
                        records_checked=records.index(record) + 1,
                        first_broken_link=record.event_id,
                    )

                # The stored prev_hash should match what we tracked
                expected_prev = prev_hash or None
                if record.prev_hash != expected_prev:
                    logger.warning(
                        "audit_prev_hash_mismatch",
                        event_id=record.event_id,
                        expected_prev=expected_prev,
                        actual_prev=record.prev_hash,
                    )
                    return AuditVerificationResult(
                        is_valid=False,
                        records_checked=records.index(record) + 1,
                        first_broken_link=record.event_id,
                    )

                prev_hash = record.entry_hash

            return AuditVerificationResult(
                is_valid=True,
                records_checked=len(records),
            )
