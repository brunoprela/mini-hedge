# Observability

Operational runbook for the mini-hedge platform. Covers what signals we
collect, where to look when things go wrong, and what to do when an alert
fires.

This document is meant to be **operational** — each section should let you
act quickly in an incident without first having to read the source.

---

## 1. Overview

We use the classic three-pillar model, with traces currently deferred:

| Pillar   | Stack                         | Status     | Source                                                    |
|----------|-------------------------------|------------|-----------------------------------------------------------|
| Metrics  | Prometheus + kube-prometheus  | Live       | [`infrastructure/prometheus/`](../infrastructure/prometheus/) |
| Logs     | Loki + Promtail               | Live       | [`infrastructure/loki/`](../infrastructure/loki/)           |
| Traces   | OpenTelemetry → Tempo/Jaeger  | **P2, not wired** | placeholder module at `app/shared/observability/telemetry.py` |
| Alerts   | Alertmanager → Slack/PagerDuty| Live       | [`infrastructure/alertmanager/`](../infrastructure/alertmanager/) |
| Dashboards| Grafana                      | Live       | [`infrastructure/grafana/dashboards/`](../infrastructure/grafana/dashboards/) |

**Tracing is a gap.** The backend calls `add_trace_id` in the structlog
pipeline (see
[`app/shared/observability/logging.py`](../app/shared/observability/logging.py)),
which surfaces a trace ID field in every log line, but there is no
exporter configured. Wiring OpenTelemetry to a real Tempo/Jaeger backend
is tracked as a P2 task in
`design/systems/hedge-fund-desk/IMPLEMENTATION.md`.

### Where each pillar is defined

- Prometheus scrape config and alert rules — [`infrastructure/prometheus/`](../infrastructure/prometheus/)
- Loki storage + retention config — [`infrastructure/loki/loki-config.yml`](../infrastructure/loki/loki-config.yml)
- Grafana dashboards (JSON, provisioned) — [`infrastructure/grafana/dashboards/`](../infrastructure/grafana/dashboards/)
- Alert routing (Slack, PagerDuty) — [`infrastructure/alertmanager/alertmanager.yml`](../infrastructure/alertmanager/alertmanager.yml)
- App-side metric definitions — [`app/shared/observability/metrics.py`](../app/shared/observability/metrics.py)
- Structured logging setup — [`app/shared/observability/logging.py`](../app/shared/observability/logging.py)

---

## 2. Metrics catalog

All metrics are defined in
[`app/shared/observability/metrics.py`](../app/shared/observability/metrics.py)
and exposed on `GET /metrics` (Prometheus text format, no auth). The
Starlette middleware `PrometheusMiddleware` instruments every HTTP
request; service code increments the business counters directly.

### HTTP (populated by middleware)

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `http_requests_total` | Counter | `method`, `path_template`, `status_code` | Total HTTP requests. Path templates have UUIDs and fund slugs normalised to `{id}` / `{slug}` to keep cardinality bounded. |
| `http_request_duration_seconds` | Histogram | `method`, `path_template` | Request duration. Use `histogram_quantile` for p50/p95/p99. |
| `http_requests_in_progress` | Gauge | `method` | Concurrent in-flight requests. Rising steadily = saturation. |

### Business

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `orders_total` | Counter | `fund_slug`, `status` | Orders created per fund. Useful to detect silent outages (no orders = no business). |

### Kafka

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `kafka_events_published_total` | Counter | `topic` | Producer-side — every successful publish. |
| `kafka_events_consumed_total` | Counter | `topic` | Consumer-side — every successful consume (after handler success). |
| `kafka_dlq_events_total` | Counter | `topic` | Events that failed handler execution and were routed to DLQ. Non-zero is always suspicious. |

### Circuit breakers

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `circuit_breaker_state` | Gauge | `circuit` | Current state: `0=CLOSED`, `1=HALF_OPEN`, `2=OPEN`. |
| `circuit_breaker_state_transitions_total` | Counter | `circuit`, `from_state`, `to_state` | Count of state changes. Frequent `CLOSED → OPEN` transitions = flaky upstream. |

### Label cardinality

Path templates are explicitly normalised (see `_normalise_path` in
`metrics.py`) — we replace UUIDs with `{id}` and the segment after
`/api/v1/funds/` with `{slug}`. Don't add a metric with a label like
`user_id` or `order_id` — cardinality will explode Prometheus's memory
usage within hours.

---

## 3. Dashboards

Provisioned under
[`infrastructure/grafana/dashboards/`](../infrastructure/grafana/dashboards/)
and loaded by Grafana at startup via the provisioning config in
`infrastructure/grafana/provisioning/dashboards/dashboards.yml`.

### `api-overview.json` — Four Golden Signals

The first dashboard to open in any incident. UID: `minihedge-api`.

| Panel                        | Metric / Query                                                                                      | When to look |
|------------------------------|------------------------------------------------------------------------------------------------------|--------------|
| Request Rate (req/s)         | `sum(rate(http_requests_total[5m]))`                                                                 | Did traffic drop? spike? |
| Error Rate (5xx %)           | `sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100` | Any alert firing? Start here. |
| Latency p50/p95/p99          | `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`              | Slow-request complaints. |
| Requests in progress         | `sum(http_requests_in_progress)`                                                                     | Saturation / stuck handlers. |
| Top endpoints by error rate  | Grouped by `path_template`                                                                           | Narrow down which route broke. |

### `business-metrics.json` — Orders, NAV, P&L

The second dashboard. UID: `minihedge-business`. Use when the API looks
healthy but something feels off.

| Panel                   | Metric                                  | When to look |
|-------------------------|------------------------------------------|--------------|
| Orders per minute       | `rate(orders_total[1m])`                 | Outside trading hours it should be 0 — if it's 0 inside trading hours, investigate. |
| Orders by status        | `sum by (status) (rate(orders_total[5m]))` | Rising `rejected` count = broker or risk-check issue. |
| Kafka events published  | `sum by (topic) (rate(kafka_events_published_total[5m]))` | A healthy app publishes continuously. Zero = stuck producer. |
| DLQ events              | `sum by (topic) (rate(kafka_dlq_events_total[5m]))`       | Non-zero is always an incident. See §9 Kafka DLQ playbook. |

### Not yet dashboarded

- NAV-calc orchestrator step timings (P1)
- Per-fund error breakdown (P2)
- Tenant-scoped SLOs (P2)

---

## 4. Alert rules

Defined in
[`infrastructure/prometheus/alert_rules.yml`](../infrastructure/prometheus/alert_rules.yml).
All alerts route through Alertmanager; severity `critical` goes to
PagerDuty, `warning` to `#ops-alerts` Slack, `info` to `#ops-info`.

| Alert | Expression | For | Severity | What it means | What to do |
|-------|------------|-----|----------|----------------|------------|
| `HighErrorRate` | `5xx rate / total > 5%` | 5m | critical | The API is returning server errors on >5% of requests. | Jump to §9 "Error rate spiking". |
| `HighLatencyP99` | `p99 > 5s` | 5m | warning | Tail latency is badly degraded. | §9 "p99 latency up". |
| `HighLatencyP95` | `p95 > 2s` | 5m | warning | Bulk latency is degraded. Often a precursor to p99 going red. | Same as above but check for slow DB queries first. |
| `KafkaDLQEventsRising` | `increase(kafka_dlq_events_total[10m]) > 0` | 1m | warning | At least one event was routed to DLQ in the last 10 minutes. | §9 "Kafka DLQ filling". |
| `NoOrdersProcessed` | `sum(increase(orders_total[30m])) == 0` | 30m | info | No orders in 30 minutes. | Usually expected outside trading hours. During trading hours: check `/health/ready`, check broker circuit breaker, check order-route ingress. |

Alert thresholds are deliberately conservative to keep signal-to-noise
high in a small ops team. Tighten them once we have SLO budgets
(§8).

---

## 5. Logs

Structured JSON via [structlog](https://www.structlog.org/). Configured in
[`app/shared/observability/logging.py`](../app/shared/observability/logging.py).
Every log line is a single JSON object on stderr, captured by the
container runtime, shipped to Loki by Promtail.

### Standard fields

Every line includes the structlog-provided fields plus our custom context:

| Field         | Source                                               | Notes |
|---------------|------------------------------------------------------|-------|
| `timestamp`   | `structlog.processors.TimeStamper(fmt="iso")`        | ISO-8601 UTC |
| `level`       | `add_log_level`                                      | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` |
| `logger`      | `add_logger_name`                                    | Dotted module path |
| `event`       | first-positional                                     | Human-readable event name — snake_case preferred |
| `trace_id`    | `add_trace_id`                                       | Placeholder today; real OTEL trace ID when wired |
| `fund_slug`   | `contextvars.merge_contextvars`                      | Bound at request entry when route has a fund scope |
| `customer_id` | `contextvars.merge_contextvars`                      | Bound at request entry |
| `request_id`  | `contextvars.merge_contextvars`                      | Per-request UUID |
| `actor_id`    | `contextvars.merge_contextvars`                      | Keycloak `sub` claim, if authenticated |

### Querying in Grafana (Loki)

Loki uses LogQL. Common queries:

```logql
# All errors in the backend over the last hour
{namespace="mini-hedge", app="mini-hedge-backend"} |= "error" | json | level="ERROR"

# All logs for a specific request
{namespace="mini-hedge"} | json | request_id="9f3b..."

# All actions for a given customer across all services
{namespace="mini-hedge"} | json | customer_id="cust_123"

# Rate of errors per fund
sum by (fund_slug) (rate({namespace="mini-hedge"} | json | level="ERROR" [5m]))

# All health-check failures
{namespace="mini-hedge"} | json | event=~"health_check_.*_failed"
```

### Retention

Loki retains 14 days hot + 30 days cold (object storage). Tune in
[`loki-config.yml`](../infrastructure/loki/loki-config.yml) under
`limits_config.retention_period`.

### Log volume hygiene

Noisy loggers are silenced in `setup_logging()`:

```
httpx, httpcore, aiokafka, hpack, opensearchpy, opensearch, elastic_transport
```

If a new library starts flooding logs, add it there rather than trying to
filter at Promtail.

---

## 6. Circuit breakers

We wrap every outbound dependency in a `CircuitBreaker`
([`app/shared/circuit_breaker.py`](../app/shared/circuit_breaker.py)) to
prevent cascading failures. Three breakers exist today:

| Circuit                | Wraps                                   | failure_threshold | recovery_timeout |
|------------------------|------------------------------------------|-------------------|------------------|
| `keycloak`             | JWT validator — JWKS fetch + token intro | 5                 | 30 s             |
| `openfga`              | Authorization checks / writes            | 5                 | 30 s             |
| `mock-exchange-broker` | Order routing to the mock exchange       | 5                 | 30 s             |

### State machine

```
CLOSED ──5 consecutive failures──► OPEN ──30s timeout──► HALF_OPEN
  ▲                                                          │
  └──────────────success on probe request──────────────┘
                                                             │
                                       failure on probe ─────┘
                                       (back to OPEN)
```

### Finding circuit state

- **Grafana** — `api-overview.json` has a panel for
  `circuit_breaker_state` (one series per circuit; `2` = OPEN).
- **Health endpoint** — `GET /health/ready` returns a `circuits` block
  with the current state of `keycloak` and `openfga`.
- **Logs** — every transition emits `circuit_breaker_state_change` with
  old_state / new_state fields.

### What to do when a circuit opens

1. **Which circuit?** Look at the Grafana panel.
2. **Is the upstream actually down?**
   - `keycloak` → check the Keycloak pod in `auth` namespace, check JWKS
     URL returns 200: `curl https://auth.minihedge.example.com/realms/minihedge/protocol/openid-connect/certs`
   - `openfga` → `kubectl -n auth port-forward svc/openfga 8080` and
     `curl localhost:8080/healthz`
   - `mock-exchange-broker` → check the `mock-exchange` deployment
3. **Once upstream is healthy**, the breaker transitions to HALF_OPEN
   after 30 s automatically. One successful request → CLOSED. No manual
   reset needed.
4. **If the breaker is flapping** (frequent CLOSED ↔ OPEN transitions),
   raise `failure_threshold` or add retry-with-backoff before the breaker
   in the caller. Don't raise `recovery_timeout` — that just makes
   recovery slower without solving the underlying flakiness.

---

## 7. Health checks

Defined in
[`app/modules/platform/routes/health.py`](../app/modules/platform/routes/health.py).

### `GET /health` — Liveness

Returns 200 + `{"status": "ok"}` whenever the process is up. **No
dependency checks.** Kubernetes uses this to decide when to kill and
restart a pod.

If this ever returns non-200, the process is deadlocked — restart the
pod.

### `GET /health/ready` — Readiness

Parallel checks against every dependency, each bounded by a 2-second
timeout. Total latency ≈ 2 s worst case.

Checks:

| Check       | What it does                                             | If skipped |
|-------------|----------------------------------------------------------|------------|
| `db`        | `SELECT 1` through the async engine                      | DB not configured |
| `kafka`     | `KafkaEventBus.health_check()`                           | Kafka bus not initialised |
| `keycloak`  | Fetch JWKS from the configured realm                     | JWT validator not configured |
| `openfga`   | `list_stores()` via the SDK client                       | OpenFGA client not initialised |
| `redis`     | `PING`                                                   | Redis not configured |

Response shape:

```json
{
  "status": "ok" | "degraded",
  "checks": {
    "db": "ok" | "down" | "timeout" | "skipped",
    "kafka": "...",
    "keycloak": "...",
    "openfga": "...",
    "redis": "..."
  },
  "circuits": { "keycloak": "CLOSED", "openfga": "CLOSED" }
}
```

Any check returning anything other than `ok` or `skipped` makes the whole
response 503. Kubernetes removes the pod from the `Service` endpoints
until it recovers.

`skipped` is treated as OK — it means the dependency isn't configured in
this environment (e.g. we don't run OpenFGA in unit-test mode).

---

## 8. SLOs (proposed)

We don't have formal SLO budgets yet. The numbers below are proposed
starting points; they'll be ratified once we have 30 days of clean
production data.

| SLI                         | SLO target (month) | Alert threshold |
|-----------------------------|--------------------|-----------------|
| p95 latency (`/api/**`)     | < 500 ms @ 99%     | p95 > 2 s for 5m |
| p99 latency                 | < 2 s @ 99%        | p99 > 5 s for 5m |
| HTTP error rate             | < 1% of requests   | > 5% for 5m     |
| Availability (`/health/ready`)| 99.5%            | 3 consecutive failures over 5 min |

**Rationale for starting conservative:** in the first 6 months we want
to learn our baseline, not burn the team with noisy pages. Once we hit
99.5% easily, tighten to 99.9% and revisit.

### Error budget policy

Once SLOs are live:

- If the monthly error budget is < 50% consumed → free to ship.
- If budget is 50–90% consumed → prioritise reliability work.
- If budget is > 90% consumed → feature freeze until the trailing 28-day
  window recovers.

---

## 9. Incident response playbooks

### "Error rate spiking" — `HighErrorRate` alert

1. Open `api-overview.json`, find the "Top endpoints by error rate" panel.
   Which `path_template` is responsible?
2. Query Loki for that path:
   ```logql
   {namespace="mini-hedge"} | json | path_template="/api/v1/funds/{slug}/orders" | level="ERROR"
   ```
3. Is it all one error class? Look at the `exc_type` / `event` fields.
4. Branch:
   - **All `DatabaseError` / `TimeoutError`** → DB problem. Check CNPG
     primary health, check `pg_stat_activity` for locks, check replica lag.
   - **All `CircuitBreakerError`** → upstream is down. Go to §6.
   - **All `ValidationError`** → a client is sending bad data, or a recent
     release changed the schema. Check recent deploys with
     `helm -n mini-hedge history mini-hedge`.
   - **Mixed / novel** → consider rollback (§10 in DEPLOYMENT.md).

### "p99 latency up" — `HighLatencyP99` or `HighLatencyP95`

1. Is it the whole API or a specific endpoint? Check the per-endpoint
   latency panel in `api-overview.json`.
2. Is the DB slow?
   ```logql
   {app="mini-hedge-backend"} | json | event="slow_query"
   ```
   Check CNPG or RDS slow-query logs. Any obvious missing index?
3. Is an external dep slow?
   - Keycloak JWKS fetch — check `circuit_breaker_state{circuit="keycloak"}`
   - OpenFGA check — `circuit_breaker_state{circuit="openfga"}`
   - Broker — `circuit_breaker_state{circuit="mock-exchange-broker"}`
4. Is the app CPU-saturated?
   ```promql
   sum(rate(container_cpu_usage_seconds_total{pod=~"mini-hedge-backend-.*"}[5m]))
   ```
   If pods sit near their CPU limit, scale out (`helm upgrade` with
   higher `maxReplicas` or lower `targetCPUUtilizationPercentage`).
5. Is a hot path thrashing? `http_requests_in_progress{method="GET"}`
   climbing = handlers are piling up. Find the slow one via the latency
   panel.

### "Circuit breaker open"

1. Which circuit? `circuit_breaker_state == 2` panel identifies it.
2. Is the upstream actually down? See §6.
3. If yes → fix the upstream; the breaker auto-recovers.
4. If no → the breaker caught something transient. Check logs for the
   `circuit_breaker_state_change` event to see how long it's been open.
5. After recovery, look at `circuit_breaker_state_transitions_total`.
   Frequent flaps → tune thresholds or add retry-with-backoff in the
   caller (see §6).

### "Kafka DLQ filling" — `KafkaDLQEventsRising`

1. Which topic?
   ```promql
   sum by (topic) (increase(kafka_dlq_events_total[15m]))
   ```
2. Which consumer group is failing?
   ```logql
   {app="mini-hedge-backend"} | json | event="event_routed_to_dlq" | topic="orders.v1"
   ```
3. What's the error? The log line carries `exc_type`, `exc_msg`,
   `payload_preview`.
4. Common causes:
   - Schema evolution broke the consumer — roll back or deploy a fixed
     consumer that tolerates both schemas.
   - Poison message (bad data) — leave it in DLQ, fix the upstream.
   - Downstream service down — fix the downstream; consumer will catch
     up once it's back.
5. Inspect DLQ contents via the admin route:
   ```
   GET /api/v1/admin/dlq?topic=orders.v1
   ```
   (see [`app/modules/platform/routes/dlq.py`](../app/modules/platform/routes/dlq.py))
6. Once upstream is fixed, **replay** DLQ messages via the admin POST
   endpoint. Don't blind-replay without confirming the underlying cause
   — you'll just re-fill the DLQ.

### "EOD run failed"

The end-of-day orchestrator (NAV calc, reconciliation, reports) runs as
a scheduled workflow.

1. Check orchestrator logs:
   ```logql
   {app="mini-hedge-backend"} | json | event=~"eod_.*" | level=~"WARNING|ERROR"
   ```
2. Identify which step failed. The orchestrator logs each step with a
   `step_name` field.
3. Common failure modes:
   - **Step "fetch_positions" failed** — DB connectivity or slow query.
   - **Step "calc_nav" failed** — missing reference data or stale market
     data. Check the adapter circuits.
   - **Step "publish_reports" failed** — email or S3 unreachable.
4. The orchestrator is idempotent per step. Fix the underlying issue and
   re-trigger via the admin API — steps that already completed are
   skipped.
5. If the EOD run **didn't start at all**, the cron trigger is the
   problem. Check the CronJob status:
   ```bash
   kubectl -n mini-hedge get cronjob
   kubectl -n mini-hedge describe cronjob mini-hedge-eod
   ```

---

## 10. Debugging locally

### Tail Prometheus metrics

With the backend running via `make up`:

```bash
curl -s http://localhost:8000/metrics | grep -E '^http_requests_total|^orders_total'
```

To watch a single metric as it changes:

```bash
watch -n 1 'curl -s http://localhost:8000/metrics | grep "orders_total"'
```

### Query Prometheus

In dev the Prometheus UI is at `http://localhost:9090`. Typical queries:

```promql
# request rate over 5m
sum(rate(http_requests_total[5m]))

# p95 latency by endpoint
histogram_quantile(0.95,
  sum by (le, path_template) (rate(http_request_duration_seconds_bucket[5m]))
)

# circuit breaker state
circuit_breaker_state
```

### Query Loki locally

Grafana at `http://localhost:3000` (admin/admin in dev). Use Explore →
Loki datasource. All LogQL examples from §5 work against the local
stack unchanged.

### Raw structlog output

When a single `docker-compose logs -f app` is too noisy:

```bash
docker compose logs -f app | jq 'select(.level == "ERROR")'
docker compose logs -f app | jq 'select(.event | startswith("health_check"))'
docker compose logs -f app | jq 'select(.fund_slug == "acme")'
```

### Traces (once OpenTelemetry is wired)

Placeholder — when we ship tracing:

- Jaeger UI will live at `http://localhost:16686` (dev)
- Every log line already carries `trace_id`; click through from Loki to
  Jaeger via Grafana's data-source linking
- Typical use: "This request was slow — what did it spend time on?"

Until then, use `http_request_duration_seconds` histogram broken down by
`path_template` to identify slow endpoints, and fall back to logs for the
per-request story.

---

## Appendix: quick-reference URLs (prod)

| Service          | URL                                               |
|------------------|---------------------------------------------------|
| Grafana          | https://grafana.minihedge.example.com             |
| Prometheus       | https://prometheus.minihedge.example.com          |
| Alertmanager     | https://alertmanager.minihedge.example.com        |
| API `/metrics`   | https://api.minihedge.example.com/metrics (scrape-only, IP-allowlisted) |
| API `/health`    | https://api.minihedge.example.com/health          |
| API `/health/ready` | https://api.minihedge.example.com/health/ready |

In staging, replace `.minihedge.example.com` with `.staging.minihedge.example.com`.
