# tests-e2e — Playwright smoke tests

One smoke test per Next.js UI. The goal is to catch regressions on the
login + primary flow *before* merge — not to be a full functional suite.

## Layout

```
tests-e2e/
  auth.setup.ts            # one-time login, writes .auth/*.json
  desk-ui.smoke.spec.ts    # ui/      — login + view portfolio
  ops-ui.smoke.spec.ts     # ops-ui/  — login + view customers
  client-ui.smoke.spec.ts  # client-ui/ — login + fund detail + subscribe wizard
  .auth/                   # gitignored; holds per-UI storageState
```

Playwright config lives at the repo root: `playwright.config.ts`. Each UI is
its own Playwright "project" with its own baseURL, storageState, and setup
dependency.

## Prerequisites

The tests assume the full platform is already running. The runner does **not**
start Next.js, Keycloak, or the API — that's too fragile. Bring the stack up
with:

```sh
make up-all
```

Expected ports (matching `.env.example`):

| UI         | URL                     | Env var            |
| ---------- | ----------------------- | ------------------ |
| desk-ui    | http://localhost:3000   | `UI_BASE_URL`      |
| ops-ui     | http://localhost:3100   | `OPS_BASE_URL`     |
| client-ui  | http://localhost:3200   | `CLIENT_BASE_URL`  |

Override any of them at the command line if needed.

## Installing Playwright

From the repo root:

```sh
pnpm install                                    # installs @playwright/test
pnpm test:e2e:install                           # downloads Chromium
# or equivalently:
npx playwright install --with-deps chromium
```

## Auth setup (Keycloak)

The smoke tests use Playwright's `storageState` strategy. `auth.setup.ts`
runs once before the smoke specs, logs in via the real Keycloak flow, and
saves a session cookie jar per UI to `tests-e2e/.auth/`.

### Auto-provisioning

The `e2e-bot` user is **auto-provisioned by `make up-all`** across all three
Keycloak realms — no manual setup needed. The seed data lives in:

- `keycloak/realm-export.json` — `minihedge` realm (desk-ui)
- `keycloak/ops-realm-export.json` — `minihedge-ops` realm (ops-ui)
- `keycloak/investors-realm-export.json` — `investors` realm (client-ui)
- `app/modules/platform/seed.py` — matching API-side user / operator /
  investor records and FGA tuples
- `SEED_SUBSCRIPTIONS` — gives the bot a capital account in the `alpha`
  fund so the client-ui subscribe wizard has something to render

The Keycloak-side password is hardcoded in the realm JSON (it's a dev-only
realm) — set `E2E_TEST_PASSWORD` to match before running:

```sh
export E2E_TEST_USER=e2e-bot
export E2E_TEST_PASSWORD=e2e-bot-password   # matches keycloak/*-realm-export.json
```

Run the setup once:

```sh
pnpm test:e2e:setup
```

You should see three `setup:*` runs pass and three JSON files appear under
`tests-e2e/.auth/`.

### Gotchas

- **ops-ui OTP is role-gated.** The `minihedge-ops` realm enforces OTP
  conditionally via a `conditional-user-role` subflow — it fires only for
  users that hold the realm role `platform_admin`. Real admin users (e.g.
  `ops-admin@minihedge.dev`) have `platform_admin` and therefore still go
  through the password + TOTP flow. The `e2e-bot` holds `ops_admin` only
  (intentionally **not** `platform_admin`), so it skips OTP and completes
  auth with username + password. See
  `keycloak/ops-realm-export.json` → the `ops-conditional-otp` subflow
  and `ops-otp-role-condition` authenticator config.
  **Do not grant `platform_admin` to service/test accounts** — that would
  re-enable mandatory OTP and break the setup again.
- **Rebuild after realm edits.** Keycloak only re-imports the realm JSON
  on a fresh start — `docker compose down -v && make up-all` (or at least
  wipe the `keycloak` schema inside `pgdata`) to apply changes.
- **API-side seed is idempotent.** Running `make up-all` repeatedly will
  not duplicate the e2e-bot's user/operator/investor records — the seeders
  short-circuit when records already exist.

### Fallback mode (no credentials)

If `E2E_TEST_USER` / `E2E_TEST_PASSWORD` aren't set, the setup writes an empty
storageState and skips. The smoke specs will then:

- Still run the "unauthenticated root redirects to /login" assertion. This is
  a real regression guard — if the middleware breaks, this catches it.
- Skip the authenticated steps with a clear message pointing to this doc.

That way the e2e suite never blocks a branch just because credentials aren't
wired up locally, but it will run end-to-end in CI where the secrets live.

## Running

```sh
pnpm test:e2e                    # run all three UIs
pnpm test:e2e --project=desk-ui  # single UI
pnpm test:e2e:ui                 # Playwright inspector UI
```

Reports land in `playwright-report/`. Videos + screenshots from failures
land in `test-results/`.

## CI

Set `CI=1` in the job env. Config switches to:
- 2 retries
- 2 workers (predictable runtime)
- HTML report artifact

Recommended job flow:
1. `make up-all` (or compose up equivalent).
2. `pnpm install`.
3. `pnpm test:e2e:install`.
4. Inject `E2E_TEST_USER` + `E2E_TEST_PASSWORD` from secrets.
5. `pnpm test:e2e`.
6. Upload `playwright-report/` on failure.
