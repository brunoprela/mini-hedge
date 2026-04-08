"""File-based alternative data provider — reads from Parquet or CSV files.

Expected directory structure::

    data_dir/
        sentiment/
            {instrument_id}.parquet  (or .csv)
        satellite/
            {instrument_id}.parquet
        ...

Each file has columns: timestamp, value, [metadata columns...]
"""

from __future__ import annotations

import asyncio
import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.adapters import AltDataRecord, SentimentRecord


class FileAltDataProvider:
    """Reads alternative data from Parquet or CSV files on disk."""

    def __init__(self, data_dir: str, source: str = "file") -> None:
        self._data_dir = Path(data_dir)
        self._source = source

    @property
    def source_name(self) -> str:
        return self._source

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_data(
        self, instrument_id: str, start: date, end: date
    ) -> list[AltDataRecord]:
        """Read data points from parquet/csv files for the given instrument and date range."""
        return await asyncio.to_thread(self._read_data, instrument_id, start, end)

    async def get_sentiment(
        self, instrument_id: str, as_of: date
    ) -> SentimentRecord | None:
        """Read sentiment from sentiment/{instrument_id}.parquet or .csv."""
        return await asyncio.to_thread(self._read_sentiment, instrument_id, as_of)

    # ------------------------------------------------------------------
    # Sync helpers (run in thread)
    # ------------------------------------------------------------------

    def _find_file(self, *parts: str) -> Path | None:
        """Locate a parquet or csv file within the data directory."""
        base = self._data_dir.joinpath(*parts)
        for ext in (".parquet", ".csv"):
            candidate = base.with_suffix(ext)
            if candidate.exists():
                return candidate
        return None

    def _read_rows(self, path: Path) -> list[dict[str, str]]:
        """Read rows from a parquet or csv file, returning list of dicts."""
        if path.suffix == ".parquet":
            return self._read_parquet(path)
        return self._read_csv(path)

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            return list(reader)

    @staticmethod
    def _read_parquet(path: Path) -> list[dict[str, str]]:
        try:
            import pyarrow.parquet as pq  # type: ignore[import-untyped]
        except ImportError as exc:
            msg = (
                "pyarrow is required to read Parquet files. "
                "Install it with: pip install pyarrow"
            )
            raise ImportError(msg) from exc

        table = pq.read_table(path)
        columns = table.column_names
        rows: list[dict[str, str]] = []
        for batch in table.to_batches():
            for i in range(batch.num_rows):
                rows.append({col: str(batch.column(col)[i].as_py()) for col in columns})
        return rows

    @staticmethod
    def _parse_timestamp(raw: str) -> datetime:
        """Best-effort timestamp parsing."""
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        msg = f"Cannot parse timestamp: {raw!r}"
        raise ValueError(msg)

    def _read_data(
        self, instrument_id: str, start: date, end: date
    ) -> list[AltDataRecord]:
        from app.shared.adapters import AltDataRecord

        records: list[AltDataRecord] = []

        # Search across all subdirectories for matching files
        for subdir in self._data_dir.iterdir():
            if not subdir.is_dir():
                continue
            file = self._find_file(subdir.name, instrument_id)
            if file is None:
                continue

            for row in self._read_rows(file):
                ts = self._parse_timestamp(row.get("timestamp", ""))
                row_date = ts.date()
                if row_date < start or row_date > end:
                    continue

                value_str = row.get("value", "0")
                metadata = {
                    k: v for k, v in row.items() if k not in ("timestamp", "value")
                }

                records.append(
                    AltDataRecord(
                        instrument_id=instrument_id,
                        timestamp=ts,
                        value=Decimal(value_str),
                        source=self._source,
                        metadata=metadata or None,
                    )
                )

        return records

    def _read_sentiment(
        self, instrument_id: str, as_of: date
    ) -> SentimentRecord | None:
        from app.shared.adapters import SentimentRecord

        file = self._find_file("sentiment", instrument_id)
        if file is None:
            return None

        rows = self._read_rows(file)
        if not rows:
            return None

        # Find the row closest to (but not after) as_of
        best_row: dict[str, str] | None = None
        best_date: date | None = None
        for row in rows:
            ts = self._parse_timestamp(row.get("timestamp", ""))
            row_date = ts.date()
            if row_date > as_of:
                continue
            if best_date is None or row_date > best_date:
                best_date = row_date
                best_row = row

        if best_row is None:
            return None

        ts = self._parse_timestamp(best_row.get("timestamp", ""))
        return SentimentRecord(
            instrument_id=instrument_id,
            source=self._source,
            timestamp=ts,
            sentiment_score=Decimal(best_row.get("sentiment_score", "0")),
            volume=int(best_row.get("volume", "0")),
            positive_mentions=int(best_row.get("positive_mentions", "0")),
            negative_mentions=int(best_row.get("negative_mentions", "0")),
            neutral_mentions=int(best_row.get("neutral_mentions", "0")),
        )
