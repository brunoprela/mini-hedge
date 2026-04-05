"""Data access for API key records."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.modules.platform.models import APIKeyRecord
from app.shared.database import TenantSessionFactory


class APIKeyRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def get_by_hash(self, key_hash: str) -> APIKeyRecord | None:
        async with self._sf() as session:
            result = await session.execute(
                select(APIKeyRecord).where(
                    APIKeyRecord.key_hash == key_hash,
                    APIKeyRecord.is_active.is_(True),
                )
            )
            record = result.scalar_one_or_none()
            if record and record.expires_at and record.expires_at < datetime.now(UTC):
                return None
            return record

    async def insert(self, record: APIKeyRecord) -> None:
        async with self._sf() as session:
            session.add(record)
            await session.commit()
