"""Authentication middleware — extracts identity and sets request context.

Pure ASGI implementation (no BaseHTTPMiddleware) for proper concurrent
request handling. BaseHTTPMiddleware serializes response reading through
an internal channel, causing ~3s delays under concurrent load.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.shared.errors import AuthenticationError, AuthorizationError
from app.shared.request_context import RequestContext, set_request_context

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from app.modules.platform.auth_service import AuthService
    from app.shared.token_revocation import TokenRevocationService

logger = structlog.get_logger()

# Paths that skip authentication
PUBLIC_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}

# Paths where the JWT is in the query string (e.g. browser EventSource API)
_QUERY_TOKEN_PATHS = {"/api/v1/stream/events"}


def _json_response(status: int, body: dict) -> tuple[int, bytes, list[tuple[bytes, bytes]]]:
    data = json.dumps(body).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(data)).encode()),
    ]
    return status, data, headers


class AuthMiddleware:
    """Pure ASGI auth middleware — no BaseHTTPMiddleware overhead."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        if path in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        # Extract app state from scope
        app = scope.get("app")
        auth_service: AuthService | None = getattr(app.state, "auth_service", None) if app else None
        if auth_service is None:
            await self._send_json(send, 503, {"detail": "Auth service unavailable"})
            return

        # Extract auth credentials
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        fund_slug_header = headers.get(b"x-fund-slug", b"").decode() or None

        # SSE endpoints pass the JWT as a query parameter (EventSource has no headers)
        query_token = None
        if path in _QUERY_TOKEN_PATHS:
            qs = scope.get("query_string", b"").decode()
            for param in qs.split("&"):
                if param.startswith("token="):
                    query_token = param[6:]
                elif param.startswith("fund_slug="):
                    fund_slug_header = fund_slug_header or param[10:]

        request_context = None
        token_str: str | None = None  # raw JWT for revocation checks
        try:
            if query_token:
                token_str = query_token
                request_context = await auth_service.authenticate_jwt(
                    query_token, fund_slug=fund_slug_header
                )
            elif auth_header.startswith("Bearer "):
                token_str = auth_header[7:]
                request_context = await auth_service.authenticate_jwt(
                    token_str, fund_slug=fund_slug_header
                )
            elif auth_header.startswith("ApiKey "):
                raw_key = auth_header[7:]
                request_context = await auth_service.authenticate_api_key(raw_key)
            else:
                api_key = headers.get(b"x-api-key", b"").decode()
                if api_key:
                    request_context = await auth_service.authenticate_api_key(api_key)
        except AuthenticationError as exc:
            await self._send_json(send, 401, {"detail": exc.message, "code": exc.code})
            return
        except AuthorizationError as exc:
            await self._send_json(send, 403, {"detail": exc.message, "code": exc.code})
            return
        except Exception:
            logger.exception("auth_middleware_error", path=path)
            await self._send_json(send, 500, {"detail": "Internal server error"})
            return

        if request_context is None:
            await self._send_json(
                send, 401, {"detail": "Authentication required", "code": "MISSING_CREDENTIALS"}
            )
            return

        # Token revocation check (graceful degradation: skip if Redis unavailable)
        revocation: TokenRevocationService | None = (
            getattr(app.state, "token_revocation", None) if app else None
        )
        if revocation is not None:
            try:
                revoked = await self._check_revocation(revocation, token_str, request_context)
                if revoked:
                    await self._send_json(
                        send, 401, {"detail": "Token has been revoked", "code": "TOKEN_REVOKED"}
                    )
                    return
            except Exception:
                # Redis down — fail open (graceful degradation)
                logger.warning("revocation_check_failed", path=path)

        set_request_context(request_context)

        # Set fund scope for per-fund schema isolation
        if request_context.fund_slug and app:
            sf = getattr(app.state, "session_factory", None)
            if sf is not None:
                async with sf.fund_scope(request_context.fund_slug):
                    await self.app(scope, receive, send)
                    return

        await self.app(scope, receive, send)

    @staticmethod
    async def _check_revocation(
        revocation: TokenRevocationService,
        token_str: str | None,
        request_context: RequestContext,
    ) -> bool:
        """Return True if the token or user session has been revoked."""
        if token_str is None:
            # API-key auth — no JWT to revoke
            return False

        import jwt as pyjwt

        try:
            # Decode without verification — the JWT was already validated above.
            payload = pyjwt.decode(token_str, options={"verify_signature": False})
        except Exception:
            return False

        jti: str | None = payload.get("jti")
        if jti and await revocation.is_revoked(jti):
            return True

        # Check user-wide revocation
        iat_raw = payload.get("iat")
        if iat_raw is not None:
            issued_at = datetime.fromtimestamp(float(iat_raw), tz=UTC)
            if await revocation.is_user_revoked_since(request_context.actor_id, issued_at):
                return True

        return False

    @staticmethod
    async def _send_json(send: Send, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(data)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": data})
