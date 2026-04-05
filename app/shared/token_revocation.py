"""JTI-based token revocation backed by Redis.

Provides two revocation strategies:
1. **Single token** — stores ``revoked:jti:{jti}`` with TTL matching token expiry.
2. **User-wide** — stores ``revoked:user:{user_id}`` with a timestamp; tokens
   issued before that timestamp are considered revoked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger()

# Redis key prefixes
_JTI_PREFIX = "revoked:jti:"
_USER_PREFIX = "revoked:user:"


class TokenRevocationService:
    """Token revocation service backed by Redis."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def revoke_token(self, jti: str, expires_at: datetime) -> None:
        """Revoke a single token by JTI.

        The key is stored with a TTL matching the token's remaining lifetime
        so revocation entries are automatically cleaned up after the token
        would have expired anyway.
        """
        now = datetime.now(UTC)
        ttl_seconds = int((expires_at - now).total_seconds())
        if ttl_seconds <= 0:
            # Token already expired — nothing to revoke.
            return
        key = f"{_JTI_PREFIX}{jti}"
        await self._redis.set(key, "1", ex=ttl_seconds)
        logger.info("token_revoked", jti=jti, ttl=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        """Check whether a specific token JTI has been revoked."""
        key = f"{_JTI_PREFIX}{jti}"
        return await self._redis.exists(key) > 0

    async def revoke_user_tokens(self, user_id: str) -> None:
        """Revoke all tokens for a user by recording the current timestamp.

        Any token with an ``iat`` before this timestamp is considered revoked.
        The key has no TTL — it persists until explicitly removed or overwritten.
        """
        now = datetime.now(UTC)
        key = f"{_USER_PREFIX}{user_id}"
        await self._redis.set(key, str(now.timestamp()))
        logger.info("user_tokens_revoked", user_id=user_id)

    async def is_user_revoked_since(self, user_id: str, issued_at: datetime) -> bool:
        """Check whether the user's tokens were invalidated after *issued_at*."""
        key = f"{_USER_PREFIX}{user_id}"
        raw = await self._redis.get(key)
        if raw is None:
            return False
        revoked_at = datetime.fromtimestamp(float(raw), tz=UTC)
        return issued_at < revoked_at
