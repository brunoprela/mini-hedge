"""Unit tests for the MinIO archival pipeline."""

from __future__ import annotations

import io

from app.shared.archival import ArchivalResult, MinioArchiver, _to_parquet_buffer


class TestParquetConversion:
    def test_converts_records_to_parquet(self) -> None:
        records = [
            {
                "event_id": "evt-001",
                "event_type": "trades.executed",
                "actor_id": "pm-001",
                "actor_type": "user",
                "fund_slug": "alpha",
                "payload": {"instrument_id": "AAPL", "quantity": 100},
                "created_at": "2024-01-15T10:30:00",
            },
            {
                "event_id": "evt-002",
                "event_type": "orders.created",
                "actor_id": "pm-002",
                "actor_type": "user",
                "fund_slug": "alpha",
                "payload": {"instrument_id": "MSFT", "quantity": 50},
                "created_at": "2024-01-15T11:00:00",
            },
        ]

        buf = _to_parquet_buffer(records)

        assert isinstance(buf, io.BytesIO)
        assert buf.getbuffer().nbytes > 0

        # Verify we can read it back with pyarrow
        import pyarrow.parquet as pq

        table = pq.read_table(buf)
        assert len(table) == 2
        assert "event_id" in table.column_names
        assert "payload" in table.column_names

    def test_empty_records(self) -> None:
        buf = _to_parquet_buffer([])
        import pyarrow.parquet as pq

        table = pq.read_table(buf)
        assert len(table) == 0


class TestMinioArchiver:
    def test_archive_empty_records_returns_zero(self) -> None:
        archiver = MinioArchiver()
        archiver._client = "placeholder"  # bypass connect check

        result = archiver.archive_month(
            fund_slug="alpha",
            year=2024,
            month=1,
            records=[],
        )

        assert result.records_archived == 0
        assert result.object_key == ""

    def test_archival_result_dataclass(self) -> None:
        result = ArchivalResult(
            object_key="alpha/2024/01.parquet",
            records_archived=150,
            size_bytes=4096,
        )
        assert result.object_key == "alpha/2024/01.parquet"
        assert result.records_archived == 150
        assert result.size_bytes == 4096
