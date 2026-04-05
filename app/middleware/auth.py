"""Authentication middleware — extracts identity and sets request context."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.shared.errors import AuthenticationError, AuthorizationError
from app.shared.request_context import set_request_context

if TYPE_CHECKING:
    from app.modules.platform.auth_service import AuthService
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()

# Paths that skip authentication
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/api/v1/stream/events"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Extracts identity from Authorization header and sets RequestContext.

    Looks up ``auth_service`` from ``request.app.state`` so it can be
    registered at module level (before the lifespan runs).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip auth for public endpoints
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # /auth/agent-token requires auth via its own dependency.

        auth_service: AuthService | None = getattr(request.app.state, "auth_service", None)
        if auth_service is None:
            return Response(
                content='{"detail":"Auth service unavailable"}',
                status_code=503,
                media_type="application/json",
            )

        try:
            ctx = await self._resolve_context(request, auth_service)
        except AuthenticationError as exc:
            return JSONResponse(
                status_code=401,
                content={"detail": exc.message, "code": exc.code},
            )
        except AuthorizationError as exc:
            return JSONResponse(
                status_code=403,
                content={"detail": exc.message, "code": exc.code},
            )
        except Exception:
            logger.exception("auth_middleware_error", path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        if ctx is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required", "code": "MISSING_CREDENTIALS"},
            )

        set_request_context(ctx)

        # Set fund scope so TenantSessionFactory sessions target the
        # correct per-fund schema for the duration of this request.
        if ctx.fund_slug:
            sf = getattr(request.app.state, "session_factory", None)
            if sf is not None:
                async with sf.fund_scope(ctx.fund_slug):
                    return await call_next(request)

        return await call_next(request)

    async def _resolve_context(self, request: Request, auth: AuthService) -> RequestContext | None:
        auth_header = request.headers.get("authorization", "")
        fund_slug = request.headers.get("x-fund-slug")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return await auth.authenticate_jwt(token, fund_slug=fund_slug)

        if auth_header.startswith("ApiKey "):
            raw_key = auth_header[7:]
            return await auth.authenticate_api_key(raw_key)

        # Also check X-API-Key header
        api_key = request.headers.get("x-api-key")
        if api_key:
            return await auth.authenticate_api_key(api_key)

        return None
