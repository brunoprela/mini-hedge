# Deployment

Production deployment guide for the mini-hedge platform.

This document describes how to ship the backend (FastAPI), the three UIs
(`desk-ui`, `ops-ui`, `client-ui`), and the Alembic migration job to staging
and production Kubernetes clusters.

For the chart-level README (file tree, security defaults, validation
commands), see [`infrastructure/k8s/README.md`](../infrastructure/k8s/README.md).

---

## 1. Overview

mini-hedge uses two different runtime topologies:

| Environment       | Runtime                                              | Managed by                          |
|-------------------|------------------------------------------------------|-------------------------------------|
| Local development | `docker-compose.yml` (Postgres, Kafka, Keycloak, …)  | `make up` (root `Makefile`)         |
| Staging / Prod    | Kubernetes + Helm                                    | `infrastructure/k8s/charts/mini-hedge/` |

The Helm umbrella chart lives at
[`infrastructure/k8s/charts/mini-hedge/`](../infrastructure/k8s/charts/mini-hedge/)
and deploys four `Deployment`s (backend + 3 UIs), an `HPA` and `PDB` per
workload, Traefik `IngressRoute`s with cert-manager TLS, a pre-upgrade
Alembic `Job` hook, and optional `ExternalSecret` / `ServiceMonitor` /
`NetworkPolicy` resources.

CI/CD is handled by
[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml), which
builds all four images in parallel, lints the chart, and runs
`helm upgrade --install --atomic --wait` against the target cluster.

### Guiding principles

1. **The chart is the source of truth.** Anything deployed outside the chart
   is drift and should be reconciled back in.
2. **No secret values in git.** Values files reference secret names; the
   actual material is loaded via External Secrets Operator (ESO) or
   SealedSecrets.
3. **Forward-only migrations.** Alembic runs as a pre-upgrade hook — if it
   fails, the Deployment is never rolled.
4. **Atomic upgrades.** `helm upgrade --atomic` means any failure
   auto-rolls-back; we never have to manually clean up a half-deployed state.

---

## 2. Prerequisites

These run **outside** the mini-hedge chart and must be present before you
can deploy. They're shared across tenants, upgraded on their own cadence,
and intentionally not coupled to the app release cycle.

| Concern              | Recommended implementation                                                   | Notes                                                  |
|----------------------|------------------------------------------------------------------------------|--------------------------------------------------------|
| Managed Postgres     | CloudNativePG operator, RDS, or AlloyDB                                      | Needs `wal_level=logical` for Debezium CDC             |
| Kafka cluster        | Strimzi operator, Confluent Cloud, or AWS MSK                                | Min. 3 brokers, replication factor 3                   |
| Keycloak             | `keycloak/keycloak` Helm chart                                               | Realm `minihedge`, clients for each UI + backend       |
| OpenFGA              | `openfga/openfga` Helm chart                                                 | Store + authorization model must be pre-seeded         |
| Redis                | `bitnami/redis` or managed                                                   | Used for rate limiting + idempotency cache             |
| Ingress + TLS        | Traefik + cert-manager with a production `ClusterIssuer`                     | Chart assumes Traefik `IngressRoute` CRDs              |
| Secrets backend      | HashiCorp Vault (preferred), AWS Secrets Manager, or GCP Secret Manager      | Accessed via External Secrets Operator                 |
| Observability stack  | kube-prometheus-stack + Loki + Grafana                                       | ServiceMonitor CRD must exist for auto-discovery       |
| Container registry   | GHCR, ECR, GAR, or self-hosted Harbor                                        | Must be reachable from nodes; pull secrets in-namespace |

### Minimum cluster versions

- Kubernetes **1.27+**
- Helm **3.12+**
- cert-manager **1.13+**
- external-secrets-operator **0.9+**

### Pre-install checklist

Before you run `helm install` the first time, verify:

```bash
# CRDs are installed
kubectl get crd | grep -E 'externalsecret|ingressroute|servicemonitor|certificate'

# Namespaces exist
kubectl get ns mini-hedge data auth observability secrets ingress

# ClusterSecretStore is configured and reachable
kubectl get clustersecretstore vault-backend -o yaml

# cert-manager ClusterIssuer is ready
kubectl get clusterissuer letsencrypt-prod -o jsonpath='{.status.conditions[0].type}'
```

---

## 3. Environments

We run two long-lived environments. There are no short-lived preview
environments yet — that's on the roadmap and will require per-PR Helm
releases against a shared staging cluster.

| Environment | Cluster                  | Database     | Domain                      | Scale                |
|-------------|--------------------------|--------------|-----------------------------|----------------------|
| `staging`   | `mini-hedge-staging`     | 1× primary   | `*.staging.minihedge.example.com` | 2 backend / 2 UI    |
| `production`| `mini-hedge-production`  | primary + replica | `*.minihedge.example.com`    | 3–20 backend / 3–10 UI |

### Values files

Each environment has a dedicated values file, **not** committed when it
contains real hostnames or references to production secret paths. The
repository ships examples:

- [`values-staging.yaml.example`](../infrastructure/k8s/charts/mini-hedge/values-staging.yaml.example)
- [`values-production.yaml.example`](../infrastructure/k8s/charts/mini-hedge/values-production.yaml.example)

Copy each `.example` to `values-<env>.yaml` in the private ops repo (or
wherever you keep deploy-time config), edit hostnames, TLS secret names,
and the `externalSecret` path, and feed it to `helm upgrade` via `-f`.

### Key differences between staging and production

| Setting                                    | Staging                              | Production                            |
|--------------------------------------------|--------------------------------------|---------------------------------------|
| `backend.autoscaling.minReplicas`          | 2                                    | 3                                     |
| `backend.autoscaling.maxReplicas`          | 6                                    | 20                                    |
| `backend.resources.requests.cpu`           | 500m                                 | 1                                     |
| `backend.podDisruptionBudget.minAvailable` | 1                                    | 2                                     |
| `backend.config.LOG_LEVEL`                 | `INFO` (or `DEBUG`)                  | `INFO`                                |
| `backend.secrets.externalSecret.enabled`   | true                                 | true                                  |
| `networkPolicy.enabled`                    | false (optional)                     | true                                  |
| `backend.serviceMonitor.enabled`           | true                                 | true                                  |
| `cert-manager.io/cluster-issuer`           | `letsencrypt-staging`                | `letsencrypt-prod`                    |

---

## 4. First-time deploy

Order of operations matters. Install the cluster add-ons first, then the
mini-hedge chart.

### 4.1 Install cluster add-ons

```bash
# cert-manager
helm repo add jetstack https://charts.jetstack.io
helm upgrade --install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace \
  --set installCRDs=true \
  --version v1.14.0

# external-secrets-operator
helm repo add external-secrets https://charts.external-secrets.io
helm upgrade --install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace \
  --version 0.9.11

# kube-prometheus-stack (if not already present)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  -n observability --create-namespace

# Traefik (if not already present)
helm repo add traefik https://traefik.github.io/charts
helm upgrade --install traefik traefik/traefik -n ingress --create-namespace
```

### 4.2 Configure the secret backend

```bash
# Register the Vault ClusterSecretStore (example — adjust to your setup)
kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "mini-hedge"
EOF
```

Provision the backend secret material in Vault at
`secret/data/mini-hedge/<env>/app` with the keys documented in
[`infrastructure/k8s/README.md#secret-management`](../infrastructure/k8s/README.md#secret-management):

```
DATABASE_URL, DATABASE_READ_URL, KEYCLOAK_CLIENT_SECRET,
OPENFGA_STORE_ID, OPENFGA_AUTH_MODEL_ID, JWT_SECRET, SENTRY_DSN
```

### 4.3 Seed Keycloak and OpenFGA

Before the backend can start, the following must exist:

- Keycloak realm `minihedge` with clients for each UI (`desk-ui`, `ops-ui`,
  `client-ui`) and a confidential backend client
- OpenFGA store + authorization model (pre-seeded via `scripts/seed-openfga.sh`
  or an equivalent init container — this is currently manual)

### 4.4 Install the mini-hedge chart

```bash
# Render locally first as a sanity check
helm template mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge \
  -f infrastructure/k8s/charts/mini-hedge/values-production.yaml \
  > /tmp/rendered.yaml
kubeconform /tmp/rendered.yaml

# Install
helm upgrade --install mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge --create-namespace \
  -f infrastructure/k8s/charts/mini-hedge/values-production.yaml \
  --set backend.image.tag=<git-sha> \
  --set migrations.image.tag=<git-sha> \
  --set uis.desk.image.tag=<git-sha> \
  --set uis.ops.image.tag=<git-sha> \
  --set uis.client.image.tag=<git-sha> \
  --atomic \
  --wait \
  --timeout 10m
```

### 4.5 Verify

```bash
# Check all workloads rolled out
kubectl -n mini-hedge get deploy

# Check the migration hook completed
kubectl -n mini-hedge get jobs -l app.kubernetes.io/component=migrations

# Hit the liveness endpoint via port-forward
kubectl -n mini-hedge port-forward svc/mini-hedge-backend 8000:8000 &
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/health/ready
```

---

## 5. Migrations strategy

**Forward-only, expand-contract, pre-upgrade hook.** These three properties
together give us zero-downtime deploys against a shared database.

### How it runs

Helm executes a `Job` annotated with `helm.sh/hook: pre-install,pre-upgrade`
at `hook-weight: 0` — see
[`templates/migrations/job.yaml`](../infrastructure/k8s/charts/mini-hedge/templates/migrations/job.yaml).
The Job runs `uv run alembic upgrade head` inside the backend image. Helm
blocks the upgrade on Job success before any `Deployment` is rolled.

- If the migration succeeds, the Deployment rollout proceeds.
- If the migration fails, Helm **aborts** the upgrade. The old pods keep
  serving traffic with the old schema. Fix the migration, push a new image,
  re-run `helm upgrade`.

Bounds:

- `activeDeadlineSeconds: 600` — migrations must finish in 10 minutes
- `backoffLimit: 1` — one retry, then fail loud
- `ttlSecondsAfterFinished: 3600` — Kubernetes reaps the Job pod after 1 h

### Expand-contract for breaking changes

Because old pods (schema N-1) and new pods (schema N) coexist during a
rolling deploy, any schema change must be readable by both versions.

1. **Expand** — add nullable columns, new tables, new indexes. Ship.
2. **Migrate data** — via the app on read or via a one-off Job.
3. **Deploy app code** that reads/writes the new column as the source of truth.
4. **Contract** — drop the old column in a later release.

Splitting this across 2–3 deploys is the cost of zero-downtime schema
change against a shared DB. There's no shortcut.

### Never run `alembic downgrade` in prod

Downgrade scripts are often incomplete (dropping a column = data loss) and
impossible to reason about when data has been written to the new schema.
Always **roll forward** — ship a new migration that reverts the change.

---

## 6. Rolling updates

### Standard release

```bash
helm upgrade mini-hedge infrastructure/k8s/charts/mini-hedge \
  -n mini-hedge \
  -f values-production.yaml \
  --set backend.image.tag=$GIT_SHA \
  --set migrations.image.tag=$GIT_SHA \
  --set uis.desk.image.tag=$GIT_SHA \
  --set uis.ops.image.tag=$GIT_SHA \
  --set uis.client.image.tag=$GIT_SHA \
  --atomic \
  --wait \
  --timeout 10m
```

Flags explained:

- `--atomic` — if any resource fails to become ready, Helm automatically
  rolls the release back to the previous revision. No half-deployed state.
- `--wait` — Helm blocks until all Deployments report `Available`.
- `--timeout 10m` — deploys that take longer than 10 minutes are considered
  failed. Typical deploy time is 2–4 minutes.

Rolling update behaviour is controlled by the `Deployment` strategy:
`maxUnavailable: 0`, `maxSurge: 1`. This means we never drop below the
current replica count, and new pods must become `Ready` before old ones
terminate.

### Zero-downtime guarantees

Zero downtime requires three things, all already configured:

1. **HPA** keeps `minReplicas ≥ 2` (staging) or `≥ 3` (prod), so we always
   have spare capacity during the rollout.
2. **PDB** (`minAvailable: 1` / `2`) blocks voluntary disruptions that
   would take the service below the threshold.
3. **Readiness probe** on `/health/ready` ensures new pods only receive
   traffic after DB, Kafka, Keycloak, OpenFGA, and Redis are all reachable.

### Rollback

```bash
# See the release history
helm -n mini-hedge history mini-hedge

# Roll back to the previous revision
helm -n mini-hedge rollback mini-hedge

# Or a specific revision
helm -n mini-hedge rollback mini-hedge 42
```

Helm rollback reverts the chart resources (Deployments, ConfigMaps, etc.)
to the values used in the target revision. It **does not** run migrations
in reverse.

### When NOT to rollback

Rollback is **unsafe** when:

- The release you're rolling back past contained a schema change that
  removed or renamed a column the old image depends on. The old pods will
  start crashing on startup or first query.
- The release changed a Kafka topic schema in a non-backwards-compatible
  way.
- The release rotated a secret key that downstream systems cached.

In any of these cases: **roll forward**. Ship a new release that fixes the
bad code, keeping the new schema.

---

## 7. Secrets management

### External Secrets Operator

Production uses ESO to sync from Vault. The chart renders an
`ExternalSecret` when `backend.secrets.externalSecret.enabled=true` — see
[`templates/backend/externalsecret.yaml`](../infrastructure/k8s/charts/mini-hedge/templates/backend/externalsecret.yaml).

The resulting flow:

```
Vault (source of truth)
  └─→ ClusterSecretStore: vault-backend
        └─→ ExternalSecret: mini-hedge-app (rendered by chart)
              └─→ Secret: mini-hedge-app  (created/refreshed by ESO)
                    └─→ backend pods (envFrom)
```

Refresh cadence is `refreshInterval: 1h` — if you rotate a secret in
Vault, it propagates within the hour. For emergency rotation, restart the
ESO controller or delete and re-create the `ExternalSecret`.

### Rotation cadence

| Secret                  | Cadence        | Notes                                             |
|-------------------------|----------------|---------------------------------------------------|
| `DATABASE_URL` password | Every 90 days  | Coordinate with DBA; update replica URL too       |
| `JWT_SECRET`            | Every 180 days | Rotate by dual-issuing — new secret first, then retire old |
| `KEYCLOAK_CLIENT_SECRET`| Every 180 days | Rotate in Keycloak, update Vault, wait for ESO sync |
| TLS certs               | Auto (cert-manager) | 90-day certs, renewed at 60                   |
| GHCR pull token         | Every 90 days  | Stored as `ghcr-credentials` imagePullSecret      |

### Never in git

The `values-*.yaml` files reference secret **names** only. Real material
lives in Vault / AWS SM / GCP SM. Any PR that introduces a literal secret
value to a values file is blocked by pre-commit (`detect-secrets`).

---

## 8. Image building & CI

[`deploy.yml`](../.github/workflows/deploy.yml) is triggered on push to
`main` touching `app/**`, `ui/**`, `ops-ui/**`, `client-ui/**`,
`packages/**`, `schemas/**`, `infrastructure/k8s/**`, or the Dockerfile.
It's also `workflow_dispatch`-enabled so you can manually deploy a
specific commit to either environment.

### Pipeline stages

1. **build** — matrix over the four images (`app`, `desk-ui`, `ops-ui`,
   `client-ui`). Each uses a multi-stage Dockerfile, buildx, gha layer
   cache, and publishes to `ghcr.io/<owner>/<repo>:<12-char-sha>` plus
   `:latest`. Images ship with SLSA provenance and an SPDX SBOM.
2. **helm-lint** — `helm lint` plus `helm template` against both
   `values-staging.yaml.example` and `values-production.yaml.example`,
   then `kubeconform` on the rendered output.
3. **deploy** — `helm upgrade --install --atomic --wait` against the
   target cluster, then waits for rollout on each Deployment and runs a
   `/health` smoke test via port-forward.

### Image tags

Immutable tags are the 12-char commit SHA (`${GITHUB_SHA::12}`). `latest`
is pushed but **never** used in chart values — always pin to a SHA. This
makes rollbacks trivial (`helm rollback`) and guarantees reproducibility.

### Concurrency

```yaml
concurrency:
  group: deploy-${{ inputs.environment || 'staging' }}
  cancel-in-progress: false
```

One deploy in-flight per environment. Subsequent deploys queue; they are
**not** cancelled — we never want to interrupt a rollout mid-flight.

---

## 9. Scaling

### Defaults

| Workload    | min | max | CPU target | Memory target |
|-------------|-----|-----|------------|---------------|
| backend     | 2   | 10  | 70%        | 80%           |
| desk-ui     | 2   | 6   | 70%        | —             |
| ops-ui      | 2   | 6   | 70%        | —             |
| client-ui   | 2   | 6   | 70%        | —             |

Production overrides: backend `3 → 20`, UIs `3 → 10`. See
[`values-production.yaml.example`](../infrastructure/k8s/charts/mini-hedge/values-production.yaml.example).

### When to tune

- **Latency rising under steady RPS** → backend is CPU-bound. Either raise
  `maxReplicas`, or lower `targetCPUUtilizationPercentage` to 60% so HPA
  scales out sooner.
- **Pods frequently OOMKilled** → raise memory `limits` and requests.
  Check the `container_memory_working_set_bytes` metric; if it sits >70% of
  the limit, bump the limit 25%.
- **HPA stuck at `maxReplicas`** → either the app is under-provisioned
  (raise `maxReplicas`) or the CPU target is too aggressive.
- **Rollouts slow under load** → `maxSurge: 1` only adds one pod at a
  time. For large fleets, bump to `maxSurge: 25%`.

Scaling the database is outside the scope of this chart — raise read
replicas or move to a larger instance class at the managed-Postgres layer.

---

## 10. Rollback playbook

**"We deployed a bad version."**

### Step 1. Stop the bleeding

```bash
# Roll back to the previous revision
helm -n mini-hedge rollback mini-hedge

# Or a specific good revision
helm -n mini-hedge history mini-hedge
helm -n mini-hedge rollback mini-hedge <REVISION>
```

This reverts Deployments, ConfigMaps, and the chart-rendered resources.
It does **not** revert migrations. If the failed release included a
migration that's incompatible with the previous image, skip to step 4.

### Step 2. Verify

```bash
kubectl -n mini-hedge get deploy
kubectl -n mini-hedge rollout status deploy/mini-hedge-backend
curl -fsS https://api.minihedge.example.com/health/ready
```

### Step 3. Diagnose

```bash
# Why did the bad pods fail?
kubectl -n mini-hedge describe pod -l app.kubernetes.io/component=backend
kubectl -n mini-hedge logs -l app.kubernetes.io/component=backend --tail=200

# What did Helm see go wrong?
helm -n mini-hedge history mini-hedge
helm -n mini-hedge get values mini-hedge --revision <BAD_REV>
```

Common causes:

- Migration ran fine, but app code has a bug → rollback works, ship a fix
- Readiness probe failing because of an upstream (Keycloak, Kafka) → check
  [`/health/ready`](../app/modules/platform/routes/health.py)
- Config drift in a secret (ESO not synced) → `kubectl get externalsecret`

### Step 4. Schema-incompatible rollback

If step 1 won't work safely:

1. Write a new Alembic migration that makes the schema compatible with
   the old image (e.g. re-add the dropped column with a default).
2. Build a new image that includes that migration.
3. `helm upgrade` with that image. The pre-upgrade hook runs the migration
   first; the old-application code runs safely after.

---

## 11. Disaster recovery

### What we back up

| Asset               | Backup method                                   | Frequency  | Retention |
|---------------------|-------------------------------------------------|------------|-----------|
| Postgres            | CloudNativePG continuous WAL + daily base backup | Continuous | 30 days   |
| Postgres            | Snapshot → S3 (cross-region)                    | Daily      | 90 days   |
| Kafka topic data    | MirrorMaker 2 to DR cluster (prod only)         | Continuous | 7 days    |
| Kafka consumer offsets | Compacted `__consumer_offsets` topic         | Continuous | —         |
| Vault KV secrets    | Raft snapshot to object storage                 | Daily      | 30 days   |
| OpenFGA store       | Logical export via `fga store export`           | Daily      | 90 days   |
| Keycloak realm      | Realm export (`kc.sh export`)                   | Weekly     | 90 days   |

### RTO / RPO targets

| Class        | RTO   | RPO       |
|--------------|-------|-----------|
| Production   | 1 hr  | 5 minutes |
| Staging      | 4 hr  | 1 hour    |

RPO 5 minutes is the CloudNativePG WAL shipping lag to S3. If the primary
dies, we restore from the most recent base backup + replay WAL forward.

### Restore procedure

Fully documented in runbook `DR-01` (ops wiki). Summary:

1. Spin up a fresh cluster (Terraform `terraform/k8s/<env>/`).
2. Restore Postgres from the latest base backup + WAL.
3. Restore Vault from Raft snapshot, unseal.
4. Re-apply external-secrets-operator and ClusterSecretStore.
5. Restore Kafka (or failover to DR cluster via MM2).
6. Restore Keycloak realm via `kc.sh import`.
7. Re-apply the mini-hedge Helm chart pinned to the same image tag that
   was running before the incident: `helm upgrade --install ... --set
   backend.image.tag=<last_known_good_sha>`.
8. Validate `/health/ready` returns 200 for all pods.
9. DNS cutover.

### DR drills

We run a tabletop DR exercise every quarter and a full restore-from-backup
drill to the DR cluster every 6 months. The drill validates:

- Backup integrity (can we actually restore?)
- Runbook accuracy (are the commands still current?)
- RTO (did we hit 1 hour? — if not, what slowed us down?)

---

## Appendix: command cheatsheet

```bash
# See what's installed
helm -n mini-hedge list

# See release history
helm -n mini-hedge history mini-hedge

# See rendered manifests for the current release
helm -n mini-hedge get manifest mini-hedge

# See values used for the current release
helm -n mini-hedge get values mini-hedge

# Diff a proposed upgrade (requires helm-diff plugin)
helm -n mini-hedge diff upgrade mini-hedge infrastructure/k8s/charts/mini-hedge \
  -f values-production.yaml --set backend.image.tag=$GIT_SHA

# Force-delete a stuck release (last resort)
helm -n mini-hedge uninstall mini-hedge --no-hooks
```
