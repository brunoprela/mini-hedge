"""Audit data archival — exports old audit records to MinIO as Parquet files.

Implements the tiered retention strategy:
  - Hot: PostgreSQL (current year, real-time queries)
  - Warm: OpenSearch (2 years, compliance search)
  - Cold: MinIO/S3 + Parquet (7 years, regulatory archives)
  - Witness: immudb (indefinite, tamper-proof verification)

The archival job:
  1. Queries a batch of audit records from PostgreSQL for a given month
  2. Converts to a Parquet file via pyarrow
  3. Uploads to MinIO (S3-compatible) with a deterministic key
  4. Returns the object key and record count for verification

Parquet files are queryable via DuckDB for ad-hoc investigations
without restoring to PostgreSQL.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()

_BUCKET = "audit-archive"


@dataclass
class ArchivalResult:
    """Summary of a single archival run."""

    object_key: str
    records_archived: int
    size_bytes: int


def _to_parquet_buffer(records: list[dict[str, Any]]) -> io.BytesIO:
    """Convert a list of audit record dicts to a Parquet-encoded buffer."""
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    # Flatten: serialize payload to JSON string for Parquet compatibility
    rows = []
    for r in records:
        rows.append(
            {
                "event_id": r["event_id"],
                "event_type": r["event_type"],
                "actor_id": r.get("actor_id"),
                "actor_type": r.get("actor_type"),
                "fund_slug": r.get("fund_slug"),
                "payload": json.dumps(r.get("payload", {}), default=str),
                "created_at": r.get("created_at"),
            }
        )

    table = pa.Table.from_pylist(rows)

    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    return buf


class MinioArchiver:
    """Archives audit data to MinIO (S3-compatible) as Parquet files."""

    def __init__(
        self,
        *,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        secure: bool = False,
    ) -> None:
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._secure = secure
        self._client: Any | None = None

    def connect(self) -> None:
        """Create the MinIO client and ensure the bucket exists."""
        from minio import Minio

        self._client = Minio(
            self._endpoint,
            access_key=self._access_key,
            secret_key=self._secret_key,
            secure=self._secure,
        )

        if not self._client.bucket_exists(_BUCKET):
            self._client.make_bucket(_BUCKET)
            logger.info("minio_bucket_created", bucket=_BUCKET)

        logger.info(
            "minio_connected",
            endpoint=self._endpoint,
            bucket=_BUCKET,
        )

    def archive_month(
        self,
        *,
        fund_slug: str,
        year: int,
        month: int,
        records: list[dict[str, Any]],
    ) -> ArchivalResult:
        """Archive a month of audit records as a Parquet file.

        Object key format: ``fund-alpha/2026/04.parquet``
        """
        if self._client is None:
            raise RuntimeError("Call connect() before using the archival store")

        if not records:
            return ArchivalResult(object_key="", records_archived=0, size_bytes=0)

        object_key = f"{fund_slug}/{year}/{month:02d}.parquet"
        buf = _to_parquet_buffer(records)
        size = buf.getbuffer().nbytes

        self._client.put_object(
            _BUCKET,
            object_key,
            buf,
            length=size,
            content_type="application/octet-stream",
        )

        logger.info(
            "audit_archived",
            fund_slug=fund_slug,
            year=year,
            month=month,
            records=len(records),
            size_bytes=size,
            object_key=object_key,
        )

        return ArchivalResult(
            object_key=object_key,
            records_archived=len(records),
            size_bytes=size,
        )

    def list_archives(self, fund_slug: str) -> list[str]:
        """List all archived Parquet files for a fund."""
        if self._client is None:
            raise RuntimeError("Call connect() before using the archival store")

        objects = self._client.list_objects(_BUCKET, prefix=f"{fund_slug}/", recursive=True)
        return [obj.object_name for obj in objects]
