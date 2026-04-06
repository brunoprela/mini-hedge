"""Archival service — orchestrates monthly audit log export to cold storage.

Coordinates the pipeline:
  1. Determine which months are eligible (completed, not yet archived)
  2. Fetch records from AuditLogRepository for each fund/month
  3. Export to MinIO via MinioArchiver
  4. Record the archival in the index table (idempotency + audit trail)
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.modules.platform.models import ArchivalRecord

if TYPE_CHECKING:
    from app.modules.platform.audit_repository import AuditLogRepository
    from app.modules.platform.fund_repository import FundRepository
    from app.shared.archival import ArchivalResult, MinioArchiver
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


def _next_month(dt: datetime) -> datetime:
    """Return the first day of the next month (stdlib, no dateutil)."""
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1, day=1)
    return dt.replace(month=dt.month + 1, day=1)


def _records_checksum(records: list[dict[str, Any]]) -> str:
    """Compute a SHA-256 checksum over event_ids for verification."""
    event_ids = sorted(r["event_id"] for r in records)
    return hashlib.sha256(json.dumps(event_ids).encode()).hexdigest()


class ArchivalService:
    """Orchestrates monthly archival of audit logs to MinIO cold storage."""

    def __init__(
        self,
        *,
        archiver: MinioArchiver,
        audit_repo: AuditLogRepository,
        fund_repo: FundRepository,
        session_factory: TenantSessionFactory,
    ) -> None:
        self._archiver = archiver
        self._audit_repo = audit_repo
        self._fund_repo = fund_repo
        self._session_factory = session_factory

    async def run_archival(self) -> list[ArchivalResult]:
        """Archive all eligible months for all active funds.

        A month is eligible when it is fully completed (current date is
        past the end of that month) and no archival record exists for it.
        """
        results: list[ArchivalResult] = []
        active_funds = await self._fund_repo.get_all_active()

        for fund in active_funds:
            fund_results = await self._archive_fund(fund.slug)
            results.extend(fund_results)

        logger.info(
            "archival_run_complete",
            funds_processed=len(active_funds),
            months_archived=len(results),
            total_records=sum(r.records_archived for r in results),
        )
        return results

    async def archive_fund_month(
        self,
        fund_slug: str,
        year: int,
        month: int,
    ) -> ArchivalResult | None:
        """Archive a specific fund/month. Returns None if already archived or no records."""
        if await self._is_archived(fund_slug, year, month):
            logger.info(
                "archival_skipped_already_done",
                fund_slug=fund_slug,
                year=year,
                month=month,
            )
            return None

        start = datetime(year, month, 1, tzinfo=UTC)
        end = _next_month(start)

        records = await self._audit_repo.get_records_for_period(
            start=start,
            end=end,
            fund_slug=fund_slug,
        )

        if not records:
            logger.info(
                "archival_skipped_no_records",
                fund_slug=fund_slug,
                year=year,
                month=month,
            )
            return None

        result = self._archiver.archive_month(
            fund_slug=fund_slug,
            year=year,
            month=month,
            records=records,
        )

        checksum = _records_checksum(records)
        await self._record_archival(fund_slug, year, month, result, checksum)

        return result

    async def _archive_fund(self, fund_slug: str) -> list[ArchivalResult]:
        """Archive all eligible months for a single fund."""
        results: list[ArchivalResult] = []
        now = datetime.now(tz=UTC)

        # Find the earliest audit record for this fund to know where to start
        count = await self._audit_repo.count_for_period(
            start=datetime(2020, 1, 1, tzinfo=UTC),
            end=now,
            fund_slug=fund_slug,
        )
        if count == 0:
            return results

        # Archive each completed month up to (but not including) the current month
        current_month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        # Start from a reasonable lookback — 2 years max
        cursor = datetime(now.year - 2, now.month, 1, tzinfo=UTC)

        while cursor < current_month_start:
            result = await self.archive_fund_month(
                fund_slug=fund_slug,
                year=cursor.year,
                month=cursor.month,
            )
            if result is not None:
                results.append(result)
            cursor = _next_month(cursor)

        return results

    async def _is_archived(self, fund_slug: str, year: int, month: int) -> bool:
        """Check if a fund/month has already been archived."""
        async with self._session_factory() as session:
            stmt = select(ArchivalRecord.id).where(
                ArchivalRecord.fund_slug == fund_slug,
                ArchivalRecord.year == year,
                ArchivalRecord.month == month,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def _record_archival(
        self,
        fund_slug: str,
        year: int,
        month: int,
        result: ArchivalResult,
        checksum: str,
    ) -> None:
        """Insert an archival index record (idempotent via unique constraint)."""
        async with self._session_factory() as session:
            stmt = insert(ArchivalRecord).values(
                fund_slug=fund_slug,
                year=year,
                month=month,
                object_key=result.object_key,
                records_archived=result.records_archived,
                size_bytes=result.size_bytes,
                checksum=checksum,
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["fund_slug", "year", "month"],
            )
            await session.execute(stmt)
            await session.commit()

    async def list_archives(self, fund_slug: str | None = None) -> list[dict[str, Any]]:
        """List all archival records, optionally filtered by fund."""
        async with self._session_factory() as session:
            stmt = select(ArchivalRecord).order_by(
                ArchivalRecord.fund_slug,
                ArchivalRecord.year.desc(),
                ArchivalRecord.month.desc(),
            )
            if fund_slug:
                stmt = stmt.where(ArchivalRecord.fund_slug == fund_slug)
            result = await session.execute(stmt)
            return [
                {
                    "fund_slug": r.fund_slug,
                    "year": r.year,
                    "month": r.month,
                    "object_key": r.object_key,
                    "records_archived": r.records_archived,
                    "size_bytes": r.size_bytes,
                    "checksum": r.checksum,
                    "archived_at": r.archived_at.isoformat(),
                }
                for r in result.scalars().all()
            ]
