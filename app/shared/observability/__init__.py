"""Observability: logging, metrics, and tracing."""

from app.shared.observability.logging import setup_logging
from app.shared.observability.metrics import (
    PrometheusMiddleware,
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
    kafka_dlq_events_total,
    kafka_events_consumed_total,
    kafka_events_published_total,
    metrics_route,
    orders_total,
)
from app.shared.observability.telemetry import add_trace_id, setup_telemetry

__all__ = [
    "PrometheusMiddleware",
    "add_trace_id",
    "http_request_duration_seconds",
    "http_requests_in_progress",
    "http_requests_total",
    "kafka_dlq_events_total",
    "kafka_events_consumed_total",
    "kafka_events_published_total",
    "metrics_route",
    "orders_total",
    "setup_logging",
    "setup_telemetry",
]
