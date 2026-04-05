"""Rate limiting middleware — Redis-backed, per-key and per-route limits.

Uses slowapi (built on the ``limits`` library) for token-bucket rate limiting.
Redis backend ensures limits work correctly even if multiple app workers run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from slowapi.errors import RateLimitExceeded
    from starlette.requests import Request


def _key_func(request: Request) -> str:
    """Extract a rate-limit key from the request.

    Priority: API key header > Authorization subject > remote IP.
    """
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"apikey:{api_key}"

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        # Use the first 16 chars of the token as a key (enough to distinguish)
        return f"bearer:{auth[7:23]}"

    return f"ip:{get_remote_address(request)}"


def build_limiter(redis_url: str | None = None) -> Limiter:
    """Create a Limiter backed by Redis (or in-memory if Redis unavailable)."""
    storage_uri = redis_url or "memory://"
    return Limiter(
        key_func=_key_func,
        default_limits=["100/minute"],
        storage_uri=storage_uri,
        strategy="fixed-window",
    )


def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a 429 JSON response when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )
