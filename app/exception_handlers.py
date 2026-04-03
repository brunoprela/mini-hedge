"""Centralized exception handlers for the FastAPI application."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
    NotFoundError,
    ValidationError,
)

logger = structlog.get_logger()


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Response:
        logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return Response(
            content='{"detail":"Internal server error"}',
            status_code=500,
            media_type="application/json",
        )

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(AuthenticationError)
    async def _authn(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(AuthorizationError)
    async def _authz(request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message, "code": exc.code})
