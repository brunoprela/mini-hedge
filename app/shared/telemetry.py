"""OpenTelemetry distributed tracing — auto-instruments FastAPI, SQLAlchemy, httpx.

All OTel imports are lazy so the packages are only required when tracing is enabled
via the OTEL_ENABLED environment variable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger()

_otel_initialized = False


def add_trace_id(logger: object, method: str, event_dict: dict[str, object]) -> dict[str, object]:
    """Structlog processor that injects the current OTel trace_id, if active."""
    if not _otel_initialized:
        return event_dict

    from opentelemetry import trace

    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.trace_id:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")

    return event_dict


def setup_telemetry(app: FastAPI) -> None:
    """Initialise OpenTelemetry tracing if enabled in settings.

    When ``otel_enabled`` is *False* (the default), this function is a no-op and
    no OTel packages are imported.
    """
    from app.config import get_settings

    settings = get_settings()
    if not settings.otel_enabled:
        return

    global _otel_initialized  # noqa: PLW0603

    # --- Lazy imports — only pulled in when tracing is enabled ----------------
    import os

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = os.environ.get("OTEL_SERVICE_NAME", "minihedge")

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # --- Auto-instrument libraries -------------------------------------------
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    _otel_initialized = True
    logger.info(
        "otel_tracing_enabled",
        service_name=service_name,
        endpoint=settings.otel_endpoint,
    )
