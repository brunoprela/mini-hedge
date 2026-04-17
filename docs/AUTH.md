# Mini Hedge — Auth Runbook

Practical guide to identity, authorization, and the operational tasks that come with them. Keep this open the next time you add a permission, onboard a fund, or stare at a 401.

## 1. Overview

Mini Hedge splits authentication (who are you?) from authorization (what can you do?):

- **Keycloak** issues OIDC tokens. Three realms separate the three audiences:
  - `minihedge` — portfolio managers, analysts, risk, compliance (desk-ui). See [keycloak/realm-export.json](../keycloak/realm-export.json).
  - `minihedge-ops` — internal fund-admin operators (ops-ui). See [keycloak/ops-realm-export.json](../keycloak/ops-realm-export.json).
  - `investors` — end-investor portal (client-ui). See [keycloak/investors-realm-export.json](../keycloak/investors-realm-export.json).
- **OpenFGA** holds the relationships — `(user → role → fund)`, `(user → member → customer)`, `(portfolio → fund)`. The FGA store name is `minihedge` by default (see [app/config.py](../app/config.py#L30-L32)).
- **FastAPI** bridges the two in [`AuthService`](../app/modules/platform/services/auth/orchestrator.py): decode the Keycloak JWT, resolve the user's customer + fund context, `list_relations` against FGA to determine the permissions for this request, and attach everything to a `RequestContext`.

Three-way invariant:
1. **Keycloak** knows who the human/service is (subject, email, realm, realm-roles).
2. **OpenFGA** knows which funds and customers they touch and in what role.
3. **App-issued tokens** (HS256) are only used for machine identities (API keys, agents). Humans always come in through Keycloak.

---

## 2. Realm configuration

| Realm | Clients | Users (seeded) | OTP policy | Notes |
| --- | --- | --- | --- | --- |
| `minihedge` | `mini-hedge-ui` (public, PKCE) | `admin@minihedge.dev`, `e2e-bot` | Conditional — required for `admin` and `portfolio_manager` | Flow: `browser-conditional-otp` subflow in [realm-export.json:107](../keycloak/realm-export.json#L107-L127) |
| `minihedge-ops` | `mini-hedge-ops-ui` | `ops-admin@minihedge.dev`, `ops-viewer@minihedge.dev`, `e2e-bot` | Conditional on `platform_admin` role — see [ops-conditional-otp subflow](../keycloak/ops-realm-export.json#L89-L105) | Tighter access-token lifespan |
| `investors` | `investor-portal` | `investor@minihedge.dev`, `e2e-bot` | Disabled by default | Lower privilege; read-only perms |

Each realm file contains: realm settings (OTP policy, session limits, brute-force protection), `roles.realm` (allowed role names), `clients` (redirect URIs, web origins), `users` (seeded for dev), `authenticationFlows`, `authenticatorConfig`.

### Add a new realm

1. Export a realm JSON from Keycloak admin console or copy an existing file in [keycloak/](../keycloak/).
2. Register it in `docker-compose.yml` under the `keycloak` service's `KC_IMPORT_REALM` / volume mount — realms in that directory are auto-imported on first boot.
3. Add the realm to `app/config.py`:
   - New: `keycloak_<name>_realm` + `keycloak_<name>_client_id` fields.
   - If customer-specific, use `keycloak_customer_realms` (JSON map — defaults `"{}"`).
4. Wire validation in [`JWTValidator`](../app/modules/platform/services/auth/jwt_validator.py) so the new issuer and audience are trusted.
5. If the new realm serves users (not operators or investors), extend [`Role`](../app/shared/auth/permissions.py#L61-L69) and the FGA model so their realm-roles map to FGA roles.

---

## 3. Role model

All role enums live in [app/shared/auth/permissions.py](../app/shared/auth/permissions.py).

### `minihedge` realm → `Role` enum

| Role (Keycloak & FGA) | Permissions granted | Grants access to |
| --- | --- | --- |
| `admin` | Everything in [`Role.ADMIN`](../app/shared/auth/permissions.py#L167-L194) | Full fund admin, can `funds:manage` |
| `portfolio_manager` | read+write positions, execute trades, create/cancel orders, write risk/cash/alpha | Daily trading |
| `analyst` | All read permissions across data domains | Research |
| `risk_manager` | Read + `risk:write` | Risk configuration |
| `compliance_officer` | Read + `compliance:write` | Rule management, resolutions |
| `viewer` | Narrow read (instruments, prices, positions, funds, orders, fx_hedging) | Auditors / sit-ins |
| `investor` | `funds:read`, `capital:read`, `positions:read`, `risk:read` | Investor portal |

### `minihedge-ops` realm → `PlatformRole` enum

| Role | Grants |
| --- | --- |
| `ops_admin` | All `platform:*` read+write perms (users, funds, operators, customers, audit, access) |
| `ops_viewer` | All `platform:*` read perms |

See [`PLATFORM_ROLE_PERMISSIONS`](../app/shared/auth/permissions.py#L136-L163).

### `investors` realm

Single role `investor`, mapped onto `Role.INVESTOR` for permission resolution.

### How roles become permissions

- **Keycloak human** — Keycloak realm-role → FGA role relation on the fund → `AuthService.list_relations` returns the `can_*` permissions → `RequestContext.permissions`.
- **API key / agent** — role is stored on the DB record → `resolve_permissions` ([permissions.py:359](../app/shared/auth/permissions.py#L359-L375)) expands roles via `ROLE_PERMISSIONS`.

---

## 4. FGA model

Defined in [app/modules/platform/fga_model.json](../app/modules/platform/fga_model.json) (FGA DSL schema version 1.1).

### Types

- `user` — human in the `minihedge` realm.
- `operator` — human in the `minihedge-ops` realm.
- `investor` — human in the `investors` realm.
- `customer` — tenant (fund manager / fund administrator).
- `platform` — singleton; `platform:global` holds operator role assignments.
- `fund` — the core resource. Object IDs are customer-qualified: `fund:{customer_id}/{fund_id}` (see [`qualify_object_id`](../app/shared/fga/client.py#L89)).
- `portfolio` — belongs to a fund via `portfolio#fund → fund:{...}`.

### Core relations on `fund`

Direct role assignments (`user` → role → `fund`): `admin`, `portfolio_manager`, `analyst`, `risk_manager`, `compliance_officer`, `viewer`.

Operator bridging (`operator` → relation → `fund`): `ops_full`, `ops_read` — assigned when a fund-admin operator is granted access to a client's fund.

Investor bridging (`investor` → `investor` → `fund`).

Customer bridging (`customer` → `fund` → `fund`): used for scoping FGA tuples by customer.

Each domain permission is a computed union (`can_read_orders`, `can_execute_trades`, etc.) with two forms:
1. **Direct grant** (`{ "this": {} }`) — explicitly assign the permission to a user (useful for break-glass or per-user grants).
2. **Computed from role** — e.g., `can_execute_trades` unions `admin` + `portfolio_manager`.

The **portfolio** type uses `tuple_to_userset` to inherit from its fund (`portfolio#viewer ← fund#admin ∪ fund#portfolio_manager ∪ ...`), which means a PM never needs an explicit per-portfolio tuple.

### Read paths

- Gate a request — `require_permission(Permission.ORDERS_CREATE)` checks `can_create_orders` via FGA.
- List a user's funds — `fga.list_objects(user="user:{id}", relation="can_read_fund", type="fund")`.
- Check a user's relations to a specific fund — `fga.list_relations(user, object, relations=FGA_FUND_PERMISSIONS)` — this is what `AuthService` calls per request.

See [`FGAClient`](../app/shared/fga/client.py) for the wrapper (includes retries, per-request check cache, circuit breaker).

---

## 5. Adding a permission

Step-by-step. All paths relative to repo root.

1. **Add to the `Permission` enum** in [`app/shared/auth/permissions.py`](../app/shared/auth/permissions.py#L71). Keep the dotted convention (`domain:action`).
2. **Grant it to roles** — add the new entry to each role's frozenset in `ROLE_PERMISSIONS` (same file).
3. **Add an FGA `can_*` relation** — edit [`app/modules/platform/fga_model.json`](../app/modules/platform/fga_model.json):
   - Under `type: fund` → `relations`, add `can_<action>_<domain>` as a `union` of roles.
   - Under `metadata.relations`, add it with `directly_related_user_types: [{ "type": "user" }]` (so it can also be directly assigned).
4. **Map it in the Permission↔FGA tables**:
   - [`FGA_FUND_PERMISSIONS`](../app/shared/auth/permissions.py#L298) — add the `can_*` string.
   - [`FGA_PERMISSION_MAP`](../app/shared/auth/permissions.py#L327) — add `"can_<...>": Permission.<NEW>`.
5. **Seed tuples if needed** — [`build_seed_fga_tuples`](../app/modules/platform/seed.py#L450) in seed.py. Only if you want explicit (non-role-derived) grants.
6. **Use it at the route** — `dependencies=[require_permission(Permission.NEW)]`.
7. **Test** — unit test under `tests/unit/platform/test_auth_service.py` or similar. Hit the route with a user missing the role and assert 403; then with one who has it and assert 200.
8. **Apply the FGA model change to your running OpenFGA** — on boot, [`app/shared/fga/startup.py`](../app/shared/fga/startup.py) writes the model; you can force a reload via `make seed` or by restarting the backend (the model is stored as a versioned authorization model in OpenFGA).

Drift guard: [`test_fga_drift`](../tests/unit/platform/test_fga_drift.py) compares `FGA_FUND_PERMISSIONS` to the relations in `fga_model.json` — so if you forget one of the steps above, CI tells you.

---

## 6. Adding a fund

The lifecycle for provisioning a new fund for an existing customer:

1. **Create the customer record** (if new) — use the admin route `POST /api/v1/platform/customers` or add to the seed. See `CustomerRecord` in [app/modules/platform/models/customer.py](../app/modules/platform/models/customer.py).
2. **Create the fund record** — `POST /api/v1/platform/funds`. Allocates `FundRecord` with `customer_id`, `slug`, `name`, `base_currency`, etc.
3. **Create the per-fund PostgreSQL schema** — the platform fund-admin service will call `CREATE SCHEMA fund_{slug}` and run schema-specific migrations. See `app.shared.fund_schema.fund_schema_name` and `app.shared.alembic_plugins`. For manual provisioning: run `alembic upgrade head` with `FUND_SLUG=<slug>` in the environment.
4. **Seed FGA tuples** — write relationship tuples:
   - `customer:{id} fund fund:{cid}/{fund_id}` (customer-scoping).
   - For each user needing access: `user:{uid} <role> fund:{cid}/{fund_id}` where role ∈ {admin, portfolio_manager, analyst, risk_manager, compliance_officer, viewer}.
   - For each portfolio: `portfolio:{cid}/{pid} fund fund:{cid}/{fund_id}`.
   - For operator access: `operator:{oid} ops_full fund:{cid}/{fund_id}` or `ops_read` for read-only.
5. **Provision the Kafka topics** — topic names derive from `fund-{slug}.*` and are auto-created by [`KafkaEventBus.ensure_topics`](../app/shared/kafka.py) on startup for the known domain events.
6. **Verify** — log in as a user with `admin` on that fund; hit `GET /api/v1/funds/{slug}`. The AuthService caches for 5 minutes — restart or call `auth_service.invalidate_caches()` if needed.

The seed script does all of steps 1–5 in one shot: `make seed` (see [app/modules/platform/seed.py](../app/modules/platform/seed.py) and [app/seed.py](../app/seed.py)).

---

## 7. E2E-bot setup

`e2e-bot` is a shared credential that exists in all three realms so a single `(E2E_TEST_USER, E2E_TEST_PASSWORD)` pair can log in to every UI.

- **Keycloak side** — declared in each realm JSON with username `e2e-bot`, email `e2e-bot@test.local`, password `e2e-bot-password`, no required actions, no OTP enrolment. See [realm-export.json:217](../keycloak/realm-export.json#L217), [ops-realm-export.json:200](../keycloak/ops-realm-export.json#L200), [investors-realm-export.json:83](../keycloak/investors-realm-export.json#L83).
- **Platform side** — [`app/modules/platform/seed.py`](../app/modules/platform/seed.py#L80-L101) defines persistent UUIDs for the bot and creates a minimal user + investor record. JIT user-sync in `AuthService` (enabled by default) links the Keycloak subject to those records on first login.
- **FGA side** — `build_seed_fga_tuples` grants the bot:
  - `user:{E2E_USER_ID}` → `portfolio_manager` → `fund:alpha` (desk-ui smoke)
  - `investor:{E2E_INVESTOR_ID}` → `investor` → `fund:alpha` (client-ui smoke)
- **Playwright side** — [tests-e2e/auth.setup.ts](../tests-e2e/auth.setup.ts) performs a full OIDC flow against each realm once per suite and stores the cookies.

### Add another shared test user

1. Add the user to each realm JSON with the same email + password.
2. Add a persistent UUID constant in `seed.py` (like `USER_E2E_BOT_ID`) and wire a record + FGA tuples.
3. Add a `setup()` block in `auth.setup.ts` that logs in against the appropriate realm and saves storage state.

---

## 8. Rotating credentials

Never check real secrets in. The dev values below are **only** good in `app_env=local`; [`Settings._validate_prod`](../app/config.py#L110-L125) rejects the default JWT secret in any non-local environment.

### App-issued JWT secret (HS256)

- Where — `JWT_SECRET` env var; read in [`Settings`](../app/config.py#L26-L28).
- When — if compromised; annual rotation.
- How — issue a new secret, push to Vault (`kv/minihedge/jwt_secret`), deploy. All app-issued tokens (API keys, agents) are invalidated; user sessions are **not** affected (those are Keycloak tokens).

### Keycloak admin

- Dev credentials ship in `docker-compose.yml`; in prod the admin password is set at chart install time (`values.yaml` → secret ref).
- Rotate via the Keycloak admin REST API or admin console → Users → admin → Credentials.

### OpenFGA store

- `fga_store_name` in [app/config.py:31](../app/config.py#L31). The actual store ID is resolved at startup via [`ensure_store`](../app/shared/fga/startup.py). If the ID is pinned in an env var, update it and re-run the model bootstrap.
- Secrets for FGA (shared secret auth, if configured) are loaded via Vault.

### Keycloak client secrets (confidential clients only)

- None of the three shipped clients are confidential (`publicClient: true`) — they use PKCE. If you add a confidential client, store its secret in Vault at `kv/minihedge/keycloak/<client_id>` and load via `load_vault_secrets` ([app/shared/vault.py](../app/shared/vault.py)).

### Keycloak realm signing keys

- Rotated automatically by Keycloak when you click "Generate new keys" in admin → Realm Settings → Keys. The app fetches JWKS on demand via `PyJWKClient` ([jwt.py](../app/shared/auth/jwt.py)) with a cache — no restart needed.

---

## 9. Incident playbook — "auth is returning 401 for everyone"

Work from the outside in. Each step should take ~30 seconds.

1. **Is Keycloak itself up?** `curl -sf $KEYCLOAK_URL/realms/minihedge/.well-known/openid-configuration`. If not → Keycloak pod logs; check DB connectivity (Keycloak → Postgres).
2. **JWKS endpoint reachable from the API pods?** `kubectl exec <api-pod> -- curl -sf $KEYCLOAK_URL/realms/minihedge/protocol/openid-connect/certs`. If not → network policy or DNS.
3. **Are tokens still valid but rejected?** Check `AuthMiddleware` logs in [app/middleware/auth.py](../app/middleware/auth.py) — look for `jwt_validation_failed` log events with the underlying `PyJWTError`.
4. **Is the FGA circuit breaker open?** Search logs for `fga_circuit_open_during_auth` (emitted in [orchestrator.py:291](../app/modules/platform/services/auth/orchestrator.py#L291)). If the FGA circuit opens, `AuthService` fails closed → every user gets 401/403. Remediation: fix FGA health, then call the admin endpoint to reset the breaker, or restart the pod.
5. **Keycloak circuit breaker open?** Same idea — search for `keycloak_circuit_open_during_auth`.
6. **Has JWT_SECRET drifted between pods?** Only applies to app-issued (API-key / agent) tokens. Redeploy with matching secret.
7. **Token revocation backend down?** [`TokenRevocationService`](../app/shared/auth/token_revocation.py) uses Redis. If Redis is unhealthy, the service should fail-open for revocation checks — but confirm by checking Redis health and logs.
8. **OpenFGA model version mismatch** — check the `openfga` logs for `authorization model not found`. Remediation: re-run model bootstrap (`python -m app.shared.fga.startup` or restart backend with `FGA_ENABLED=true`).
9. **Clock skew** — a missed NTP sync on a Keycloak or API node can expire tokens immediately. Check `chronyc tracking` / `timedatectl`.

Useful correlations in Loki:
- `{app="mini-hedge-api"} |= "jwt_validation_failed"`
- `{app="mini-hedge-api"} |= "fga_check_failed"`
- `{app="keycloak"} |~ "ERROR|WARN"`

Prometheus alerts to look at: `HighErrorRate` on the `/api/v1/*` surface ([alert_rules.yml](../infrastructure/prometheus/alert_rules.yml)).

---

## 10. Common gotchas

- **OTP is conditional on role.** In `minihedge`, OTP is only required for `admin` and `portfolio_manager` (see `browser-conditional-otp` subflow in [realm-export.json:107](../keycloak/realm-export.json#L107)). In `minihedge-ops`, OTP is required only for `platform_admin`. If you add a new sensitive role, update the `authenticatorConfig` entry — otherwise users bypass OTP silently.
- **Fund schema translation is lazy.** `TenantSessionFactory` only rewrites schemas for ORM models declared under `schema="positions"`. If you add a new module that needs per-fund isolation, **you must** set `__table_args__ = {"schema": "positions"}` on its models — not `"fund"` or your module name. See [app/shared/database.py:42](../app/shared/database.py#L42).
- **Customer containment is a hard fence, not a soft check.** `require_permission` enforces it before any permission check ([permissions.py:414](../app/shared/auth/permissions.py#L414-L422)). A user with `admin` on fund A cannot access fund B even if you "forget" to add the check — good — but also cannot be granted a cross-customer bypass. Fund-admin operators who need to act across customers must set `acting_as_customer_id` via the `X-Acting-As-Customer` header.
- **`AuthService` has TTL caches on users, funds, and customers.** Default TTL is 5 minutes; cache key is `customer_id`. If you rotate a user's roles in Keycloak or rewrite FGA tuples, expect up to 5 minutes of lag in production. Call the service's `invalidate_caches` method (or restart) for immediate effect.
- **FGA object IDs are customer-qualified.** `fund:{customer_id}/{fund_id}`. Helpers: [`qualify_object_id`](../app/shared/fga/client.py#L89), [`unqualify_object_id`](../app/shared/fga/client.py#L100). Writing raw `fund:<uuid>` tuples will silently fail permission checks.
- **The BFF proxy never returns the token to the browser.** If you find yourself reading `session.accessToken` in a client component, you're on the wrong path — call the BFF at `/api/proxy/...` and it will inject the token server-side ([ui/src/app/api/proxy/[...path]/route.ts](../ui/src/app/api/proxy/[...path]/route.ts)).
- **Platform operators have `customer_id = None` by default.** Only after they select a customer (via header or path) does the middleware set it. Don't assume `request_context.customer_id` is always populated for operator routes.
- **`SYSTEM_CONTEXT` is a real context.** Startup code, seeds, and some Kafka handlers run under `SYSTEM_CONTEXT` with `actor_type = SYSTEM` ([request_context.py:96](../app/shared/auth/request_context.py#L96)). `get_actor_context` rejects it with 401 — so you cannot accidentally expose system-only code paths via HTTP.
- **`e2e-bot` uses the literal password `e2e-bot-password` in dev realms.** If you change the realm JSON, also update the Playwright env and any CI secrets. Never promote these JSON files to a prod realm import.
- **Schema registry versions are explicit, not inferred.** If you add an event, bump the topic suffix (`-v1` → `-v2`) rather than mutating the existing `.avsc`. Old consumers won't crash; they'll just skip the new topic.
