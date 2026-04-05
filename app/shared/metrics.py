"""Prometheus metrics — Four Golden Signals + business metrics.

Exposes a Starlette middleware that instruments every HTTP request and
module-level metric singletons that services increment directly.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.requests import Request

# ---------------------------------------------------------------------------
# HTTP request metrics (populated by middleware)
# ---------------------------------------------------------------------------

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path_template"],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method"],
)

# ---------------------------------------------------------------------------
# Business metrics (updated by services)
# ---------------------------------------------------------------------------

orders_total = Counter(
    "orders_total",
    "Total orders created",
    ["fund_slug", "status"],
)

kafka_events_published_total = Counter(
    "kafka_events_published_total",
    "Total Kafka events published",
    ["topic"],
)

kafka_events_consumed_total = Counter(
    "kafka_events_consumed_total",
    "Total Kafka events consumed",
    ["topic"],
)

kafka_dlq_events_total = Counter(
    "kafka_dlq_events_total",
    "Total Kafka events sent to DLQ",
    ["topic"],
)

# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _normalise_path(path: str) -> str:
    """Replace dynamic segments so cardinality stays bounded.

    - UUIDs (36-char hex-and-hyphens) become ``{id}``
    - The segment right after ``/api/v1/funds/`` is a fund slug — replace with ``{slug}``
    """
    # Replace UUIDs first
    path = _UUID_RE.sub("{id}", path)

    # Normalise fund slug: /api/v1/funds/<slug>/...
    parts = path.split("/")
    for i, part in enumerate(parts):
        if part == "funds" and i + 1 < len(parts) and parts[i + 1] not in ("{id}", ""):
            parts[i + 1] = "{slug}"
    return "/".join(parts)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Instrument every HTTP request with Prometheus counters/histograms."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        method = request.method
        http_requests_in_progress.labels(method=method).inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # If the downstream handler raises, record a 500
            duration = time.perf_counter() - start
            path_template = _normalise_path(request.url.path)
            labels = http_request_duration_seconds.labels(
                method=method, path_template=path_template
            )
            labels.observe(duration)
            http_requests_total.labels(
                method=method, path_template=path_template, status_code="500"
            ).inc()
            raise
        finally:
            http_requests_in_progress.labels(method=method).dec()

        duration = time.perf_counter() - start
        path_template = _normalise_path(request.url.path)
        http_request_duration_seconds.labels(method=method, path_template=path_template).observe(
            duration
        )
        http_requests_total.labels(
            method=method, path_template=path_template, status_code=str(response.status_code)
        ).inc()

        return response


# ---------------------------------------------------------------------------
# /metrics endpoint (plain Starlette route — bypasses auth)
# ---------------------------------------------------------------------------


async def metrics_route(request: Request) -> Response:  # noqa: ARG001
    """Return Prometheus text exposition format."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
