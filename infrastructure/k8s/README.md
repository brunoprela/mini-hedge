# mini-hedge — Kubernetes deployment

This directory holds the production-grade Helm chart for the mini-hedge
platform. It replaces `docker-compose.yml` for any environment beyond local
development.

```
infrastructure/k8s/
├── README.md                        # you are here
└── charts/
    └── mini-hedge/                  # umbrella chart for app + UIs
        ├── Chart.yaml
        ├── values.yaml              # defaults
        ├── values-staging.yaml.example
        ├── values-production.yaml.example
        └── templates/
            ├── _helpers.tpl
            ├── NOTES.txt
            ├── serviceaccount.yaml
            ├── networkpolicy.yaml
            ├── backend/             # FastAPI deployment, svc, hpa, pdb, ingress, cm, es
            ├── ui/                  # desk-ui + ops-ui + client-ui (templated)
            └── migrations/          # alembic pre-upgrade Helm hook job
```

---

## Deployment topology

**Assumption:** a single Kubernetes cluster per environment (`staging`,
`production`). No multi-region active-active in this chart — if you need that,
deploy the chart once per region and put a global load balancer + Aurora-style
database in front. HA within a region is provided by:

- HPA (2→10 backend pods, 2→6 per UI by default)
- PDB (`minAvailable: 1` dev, `2` prod)
- Pod anti-affinity + topology-spread across zones
- Rolling deploys with `maxUnavailable: 0`

### Namespaces (recommended layout)

| Namespace  | Workloads                                                |
|------------|----------------------------------------------------------|
| `mini-hedge` | app, UIs, migrations (this chart)                      |
| `data`     | Postgres (CloudNativePG), Kafka (Strimzi), Redis         |
| `auth`     | Keycloak, OpenFGA                                        |
| `observability` | kube-prometheus-stack, Loki, Grafana, Alertmanager  |
| `ingress`  | Traefik (or your ingress controller)                     |
| `secrets`  | external-secrets-operator, cert-manager                  |

The chart's default `values.yaml` references the services above using their
in-cluster FQDNs (`<svc>.<ns>.svc.cluster.local`). Override in your
`values-<env>.yaml` for managed services.

---

## Prerequisites

Install these **before** `helm install` — they're external to this chart by
design so each can be upgraded independently and shared across apps.

| Concern        | Recommended                                                               |
|----------------|---------------------------------------------------------------------------|
| Postgres       | [CloudNativePG](https://cloudnative-pg.io/) operator, **or** a managed DB (RDS, AlloyDB). The app needs `wal_level=logical` for CDC. |
| Kafka          | [Strimzi](https://strimzi.io/) operator, **or** Confluent Cloud / MSK.     |
| Keycloak       | [keycloak/keycloak](https://github.com/keycloak/keycloak-charts) Helm chart. |
| OpenFGA        | [openfga/openfga](https://github.com/openfga/helm-charts) Helm chart.      |
| Redis          | [bitnami/redis](https://artifacthub.io/packages/helm/bitnami/redis).       |
| Observability  | [prometheus-community/kube-prometheus-stack](https://github.com/prometheus-community/helm-charts). |
| Ingress        | [Traefik](https://github.com/traefik/traefik-helm-chart) (chart assumes `IngressRoute` CRDs). |
| TLS certs      | [cert-manager](https://cert-manager.io/) + a `ClusterIssuer`.              |
| Secrets        | [external-secrets.io](https://external-secrets.io/) + Vault / AWS SM / GCP SM. |

Minimum cluster versions: Kubernetes **1.27+**, Helm **3.12+**.

> **Known gap:** `client-ui/Dockerfile` (production) is not yet present in the
> repo — `ui/Dockerfile` and `ops-ui/Dockerfile` are. Copy one as a template
> before running `.github/workflows/deploy.yml`, or disable the client-ui via
> `--set uis.client.enabled=false` until it's built.

---

## Secret management

This chart intentionally does **not** render raw `Secret` manifests. Provide
`mini-hedge-app` (name is configurable via `backend.secrets.appSecretName`)
containing at minimum:

```
DATABASE_URL          # postgresql+asyncpg://user:pass@host/db?sslmode=require
DATABASE_READ_URL     # same, pointing at replica — optional
KEYCLOAK_CLIENT_SECRET
OPENFGA_STORE_ID
OPENFGA_AUTH_MODEL_ID
JWT_SECRET
SENTRY_DSN            # optional
```

Three recommended ways to provision it:

### 1. external-secrets.io (recommended for prod)

Set in your values file:

```yaml
backend:
  secrets:
    externalSecret:
      enabled: true
      secretStoreRef:
        kind: ClusterSecretStore
        name: vault-backend
      dataFrom:
        - extract:
            key: secret/data/mini-hedge/production/app
```

The chart renders an `ExternalSecret` which syncs from Vault/AWS-SM/etc. and
creates the `mini-hedge-app` Secret in-namespace.

### 2. SealedSecrets

```bash
kubectl create secret generic mini-hedge-app \
  --from-literal=DATABASE_URL='postgresql+asyncpg://...' \
  --from-literal=JWT_SECRET='...' \
  --dry-run=client -o yaml \
  | kubeseal --controller-namespace kube-system -o yaml \
  > overlays/production/sealed-secret.yaml
```

Commit the `SealedSecret`, apply separately from the chart.

### 3. Manual (dev / staging only)

```bash
kubectl -n mini-hedge create secret generic mini-hedge-app \
  --from-env-file=.env.production
```

---

## Deployment

### First-time install

```bash
# 1. Create the namespace
kubectl create namespace mini-hedge

# 2. Provision the app secret (see above)
kubectl -n mini-hedge apply -f path/to/sealed-secret.yaml

# 3. Lint + render the chart locally
helm lint infrastructure/k8s/charts/mini-hedge \
  -f infrastructure/k8s/charts/mini-hedge/values-production.yaml

helm template mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge \
  -f infrastructure/k8s/charts/mini-hedge/values-production.yaml \
  > /tmp/rendered.yaml

# 4. Install
helm upgrade --install mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge \
  -f infrastructure/k8s/charts/mini-hedge/values-production.yaml \
  --set backend.image.tag=<sha-or-semver> \
  --set migrations.image.tag=<sha-or-semver> \
  --set uis.desk.image.tag=<sha-or-semver> \
  --set uis.ops.image.tag=<sha-or-semver> \
  --set uis.client.image.tag=<sha-or-semver> \
  --wait --timeout 10m
```

### Upgrade cycle (production)

```bash
helm upgrade mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge \
  -f infrastructure/k8s/charts/mini-hedge/values-production.yaml \
  --set backend.image.tag=$GIT_SHA \
  --set migrations.image.tag=$GIT_SHA \
  --set uis.desk.image.tag=$GIT_SHA \
  --set uis.ops.image.tag=$GIT_SHA \
  --set uis.client.image.tag=$GIT_SHA \
  --atomic \
  --wait --timeout 10m
```

`--atomic` auto-rolls back if the upgrade fails.

---

## Migration strategy

Migrations run as a **pre-install, pre-upgrade Helm hook** Job:

- `helm.sh/hook`: `pre-install,pre-upgrade`
- `helm.sh/hook-delete-policy`: `before-hook-creation,hook-succeeded`
- `helm.sh/hook-weight`: `0` (lowest — runs before any other hook)

The Job executes `uv run alembic upgrade head` inside the same image as the
backend. Helm blocks the upgrade on Job success before rolling the Deployment.

### Forward-only, backwards-compatible

Follow the standard expand/contract pattern:

1. **Expand** — add new columns/tables, nullable or with defaults. Ship.
2. **Migrate data** — in the app or via a one-off Job.
3. **Contract** — drop old columns in a later release.

This ensures that if N-1 and N pods are running simultaneously during a rolling
deploy, neither sees a broken schema.

### If a migration fails

The Helm upgrade **aborts** and the Deployment is not rolled. Fix the
migration, push a new image, re-run `helm upgrade`. The old pods keep serving
traffic.

### Skipping migrations (emergency only)

```bash
helm upgrade mini-hedge . --set migrations.enabled=false ...
```

---

## Rollback

### Application rollback (no schema changes)

```bash
helm -n mini-hedge history mini-hedge
helm -n mini-hedge rollback mini-hedge <REVISION>
```

Note: Helm rollback **does not run migrations in reverse**. Only safe when the
schema is backwards compatible with the older image (which is guaranteed if
you followed expand/contract).

### Application rollback (with schema changes)

1. Run a new migration that reverts the schema forward (e.g. re-adds the
   dropped column with a backfill).
2. Ship the older image alongside that migration.

**Never** run `alembic downgrade` against production — it's a recipe for data
loss. Roll forward.

---

## Observability

The backend exposes:

- `GET /health`         — liveness
- `GET /health/ready`   — readiness (checks DB, Kafka, OpenFGA)
- `GET /metrics`        — Prometheus metrics

Enable the `ServiceMonitor` with `backend.serviceMonitor.enabled=true` so
kube-prometheus-stack picks it up automatically.

Pod annotations `prometheus.io/scrape=true` are also set for clusters that
prefer annotation-based scraping.

---

## Security defaults

- All containers run as **non-root** (UID 1000 for app, 1001 for UIs).
- **read-only** root filesystem (tmp + `.next/cache` mounted via emptyDir).
- `allowPrivilegeEscalation: false`, all capabilities dropped.
- `seccompProfile: RuntimeDefault`.
- ServiceAccount has `automountServiceAccountToken: false` (no API access
  by default — opt-in per workload if you need it).
- Optional default-deny `NetworkPolicy` via `networkPolicy.enabled=true`.
- No host network, host PID, or host path mounts anywhere in the chart.

---

## Validation

```bash
# Lint — must return 0 warnings/errors
helm lint infrastructure/k8s/charts/mini-hedge

# Render with staging values
helm template mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge \
  -f infrastructure/k8s/charts/mini-hedge/values-staging.yaml.example

# Render with production values
helm template mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge \
  -f infrastructure/k8s/charts/mini-hedge/values-production.yaml.example

# Validate against live cluster (dry-run, server-side)
helm upgrade --install mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge --dry-run --debug \
  -f infrastructure/k8s/charts/mini-hedge/values-staging.yaml.example
```

---

## Files created by this chart (summary)

Per release, with defaults:

| Kind                    | Count | Notes                                            |
|-------------------------|-------|--------------------------------------------------|
| `Deployment`            | 4     | backend + desk-ui + ops-ui + client-ui           |
| `Service`               | 4     | ClusterIP for each                               |
| `HorizontalPodAutoscaler` | 4   | CPU-targeted; backend also tracks memory         |
| `PodDisruptionBudget`   | 4     | `minAvailable: 1` by default                     |
| `IngressRoute`          | 4     | Traefik CRD; or plain Ingress if configured      |
| `ConfigMap`             | 1     | backend non-secret config                        |
| `ServiceAccount`        | 1     | shared across components                         |
| `Job` (hook)            | 1     | alembic migrations, pre-install/pre-upgrade      |
| `ExternalSecret`        | 0/1   | only if `backend.secrets.externalSecret.enabled` |
| `NetworkPolicy`         | 0/2   | only if `networkPolicy.enabled`                  |
| `ServiceMonitor`        | 0/1   | only if `backend.serviceMonitor.enabled`         |
