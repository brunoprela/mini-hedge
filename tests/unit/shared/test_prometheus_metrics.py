"""Prometheus HTTP instrumentation — /metrics exposition format tests.

Builds a minimal FastAPI app wired with ``PrometheusMiddleware`` and the
``metrics_route`` handler (no lifespan, no Kafka, no DB). Exercises a few
endpoints via ``TestClient`` and asserts the Prometheus text-format
response contains the metric names alert_rules.yml expects.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.routing import Route

from app.shared.observability.metrics import (
    PrometheusMiddleware,
    _normalise_path,
    metrics_route,
)


def _build_app() -> FastAPI:
    """Minimal FastAPI app with just Prometheus wiring — no other middleware."""
    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)
    app.routes.append(Route("/metrics", metrics_route))

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("synthetic-500")

    @app.get("/api/v1/funds/{slug}/positions")
    async def fund_positions(slug: str) -> dict[str, str]:
        return {"slug": slug}

    return app


class TestPrometheusExposition:
    def test_metrics_endpoint_returns_prometheus_text_format(self) -> None:
        app = _build_app()
        client = TestClient(app)

        # Hit a few endpoints to generate metric samples
        client.get("/ping")
        client.get("/ping")
        client.get("/api/v1/funds/acme-capital/positions")

        resp = client.get("/metrics")
        assert resp.status_code == 200
        # Prometheus text-format content type
        assert "text/plain" in resp.headers["content-type"]

        body = resp.text
        # Counter exposed with HELP + TYPE lines
        assert "# HELP http_requests_total" in body
        assert "# TYPE http_requests_total counter" in body
        # Histogram (bucket/sum/count series used by histogram_quantile)
        assert "# TYPE http_request_duration_seconds histogram" in body
        assert "http_request_duration_seconds_bucket" in body
        assert "http_request_duration_seconds_sum" in body
        assert "http_request_duration_seconds_count" in body
        # Gauge for in-flight requests
        assert "# TYPE http_requests_in_progress gauge" in body

    def test_request_counter_increments_with_status_code_label(self) -> None:
        app = _build_app()
        client = TestClient(app)

        client.get("/ping")
        client.get("/ping")

        body = client.get("/metrics").text
        # method/path_template/status_code labels — alert_rules.yml queries status_code
        assert 'http_requests_total{method="GET",path_template="/ping",status_code="200"}' in body

    def test_500_errors_recorded_for_alert_rule_query(self) -> None:
        app = _build_app()
        # TestClient re-raises by default; disable to capture the 500 response
        client = TestClient(app, raise_server_exceptions=False)

        client.get("/boom")

        body = client.get("/metrics").text
        # HighErrorRate alert depends on status_code=~"5.."
        assert 'status_code="500"' in body
        assert "/boom" in body

    def test_fund_slug_normalised_to_template(self) -> None:
        app = _build_app()
        client = TestClient(app)

        client.get("/api/v1/funds/acme-capital/positions")
        client.get("/api/v1/funds/globex-partners/positions")

        body = client.get("/metrics").text
        # Cardinality guard — both requests collapse onto the template path
        assert "/api/v1/funds/{slug}/positions" in body
        assert "acme-capital" not in body
        assert "globex-partners" not in body


class TestPathNormalisation:
    def test_uuid_segment_replaced(self) -> None:
        assert (
            _normalise_path("/api/v1/orders/550e8400-e29b-41d4-a716-446655440000")
            == "/api/v1/orders/{id}"
        )

    def test_fund_slug_replaced(self) -> None:
        assert (
            _normalise_path("/api/v1/funds/acme-capital/positions")
            == "/api/v1/funds/{slug}/positions"
        )

    def test_root_and_static_paths_untouched(self) -> None:
        assert _normalise_path("/health") == "/health"
        assert _normalise_path("/metrics") == "/metrics"
