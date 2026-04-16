"""Price data persistence."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.models.price import PriceRecord
from app.shared.repository import BaseRepository


class PriceRepository(BaseRepository):
    async def get_latest(
        self, instrument_id: str, *, session: AsyncSession | None = None
    ) -> PriceRecord | None:
        async with self._session(session) as session:
            stmt = (
                select(PriceRecord)
                .where(PriceRecord.instrument_id == instrument_id)
                .order_by(PriceRecord.timestamp.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_history(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> list[PriceRecord]:
        async with self._session(session) as session:
            stmt = (
                select(PriceRecord)
                .where(
                    PriceRecord.instrument_id == instrument_id,
                    PriceRecord.timestamp >= start,
                    PriceRecord.timestamp <= end,
                )
                .order_by(PriceRecord.timestamp)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_ohlcv_bars(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
        interval: str = "1 day",
        *,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        """Return OHLCV bars for an instrument over a time range.

        Uses ``time_bucket`` if TimescaleDB is available, otherwise falls
        back to ``date_trunc`` for standard PostgreSQL.

        Args:
            instrument_id: ticker symbol
            start: inclusive start timestamp
            end: inclusive end timestamp
            interval: bucket width (e.g. '1 hour', '1 day', '5 minutes')

        Returns:
            List of dicts with keys: period_start, open, high, low, close, volume
        """
        async with self._session(session) as session:
            # Try time_bucket (TimescaleDB), fall back to date_trunc
            try:
                stmt = text("""
                    SELECT
                        time_bucket(:interval, "timestamp") AS period_start,
                        time_bucket(:interval, "timestamp") + :interval::interval AS period_end,
                        (array_agg(mid ORDER BY "timestamp" ASC))[1] AS open,
                        MAX(ask) AS high,
                        MIN(bid) AS low,
                        (array_agg(mid ORDER BY "timestamp" DESC))[1] AS close,
                        SUM(COALESCE(volume, 0)) AS volume
                    FROM market_data.prices
                    WHERE instrument_id = :instrument_id
                      AND "timestamp" >= :start
                      AND "timestamp" <= :end
                    GROUP BY period_start, period_end
                    ORDER BY period_start
                """)
                result = await session.execute(
                    stmt,
                    {
                        "interval": interval,
                        "instrument_id": instrument_id,
                        "start": start,
                        "end": end,
                    },
                )
            except Exception as exc:
                # Fallback for standard PostgreSQL (no time_bucket).
                # Only fall back on ProgrammingError (missing function);
                # re-raise connection errors, permission errors, etc.
                from sqlalchemy.exc import ProgrammingError

                if not isinstance(exc, ProgrammingError):
                    raise
                await session.rollback()
                # Map interval string to date_trunc unit
                _interval_lower = interval.lower()
                if "day" in _interval_lower:
                    unit = "day"
                elif "hour" in _interval_lower:
                    unit = "hour"
                elif "min" in _interval_lower:
                    unit = "minute"
                elif "week" in _interval_lower:
                    unit = "week"
                elif "month" in _interval_lower:
                    unit = "month"
                else:
                    unit = "hour"
                stmt = text(f"""
                    SELECT
                        date_trunc(:unit, "timestamp") AS period_start,
                        date_trunc(:unit, "timestamp") + :interval::interval AS period_end,
                        (array_agg(mid ORDER BY "timestamp" ASC))[1] AS open,
                        MAX(ask) AS high,
                        MIN(bid) AS low,
                        (array_agg(mid ORDER BY "timestamp" DESC))[1] AS close,
                        SUM(COALESCE(volume, 0)) AS volume
                    FROM market_data.prices
                    WHERE instrument_id = :instrument_id
                      AND "timestamp" >= :start
                      AND "timestamp" <= :end
                    GROUP BY period_start, period_end
                    ORDER BY period_start
                """)
                result = await session.execute(
                    stmt,
                    {
                        "unit": unit,
                        "interval": interval,
                        "instrument_id": instrument_id,
                        "start": start,
                        "end": end,
                    },
                )

            rows = result.all()
            return [
                {
                    "period_start": row.period_start,
                    "period_end": row.period_end,
                    "open": Decimal(str(row.open)) if row.open is not None else Decimal(0),
                    "high": Decimal(str(row.high)) if row.high is not None else Decimal(0),
                    "low": Decimal(str(row.low)) if row.low is not None else Decimal(0),
                    "close": Decimal(str(row.close)) if row.close is not None else Decimal(0),
                    "volume": Decimal(str(row.volume)) if row.volume is not None else Decimal(0),
                }
                for row in rows
            ]

    async def insert(self, record: PriceRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            stmt = (
                pg_insert(PriceRecord)
                .values(
                    timestamp=record.timestamp,
                    instrument_id=record.instrument_id,
                    bid=record.bid,
                    ask=record.ask,
                    mid=record.mid,
                    volume=record.volume,
                    source=record.source,
                )
                .on_conflict_do_nothing(
                    index_elements=["timestamp", "instrument_id"],
                )
            )
            await session.execute(stmt)
            await session.commit()
