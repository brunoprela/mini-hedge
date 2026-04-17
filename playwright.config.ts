import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

/**
 * Playwright config for the mini-hedge monorepo smoke suites.
 *
 * One project per UI so they run in isolation with their own baseURL and
 * (when auth is enabled) their own storageState. Tests assume the UI servers
 * and Keycloak are already running — typically via `make up-all` — see
 * tests-e2e/README.md for the expected setup.
 */

const CI = !!process.env.CI;

const UI_BASE_URL = process.env.UI_BASE_URL ?? "http://localhost:3000";
const OPS_BASE_URL = process.env.OPS_BASE_URL ?? "http://localhost:3100";
const CLIENT_BASE_URL = process.env.CLIENT_BASE_URL ?? "http://localhost:3200";

const AUTH_DIR = path.join(__dirname, "tests-e2e", ".auth");
const DESK_STORAGE = path.join(AUTH_DIR, "desk.json");
const OPS_STORAGE = path.join(AUTH_DIR, "ops.json");
const CLIENT_STORAGE = path.join(AUTH_DIR, "client.json");

export default defineConfig({
  testDir: "./tests-e2e",
  // Ignore the .auth dir — it only holds storageState JSON, not specs.
  testIgnore: ["**/.auth/**"],

  /* Run files in parallel. Tests inside a single file run serially. */
  fullyParallel: true,

  /* Fail fast on CI if someone accidentally committed .only. */
  forbidOnly: CI,

  retries: CI ? 2 : 0,

  /* Cap workers on CI to keep things predictable. */
  workers: CI ? 2 : undefined,

  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",

  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },

  projects: [
    /* ----------------------------------------------------------------- */
    /* Shared auth setup — logs in once per UI and saves storageState.   */
    /* Individual smoke projects depend on the matching setup project.   */
    /* ----------------------------------------------------------------- */
    {
      name: "setup:desk",
      testMatch: /auth\.setup\.ts/,
      use: { baseURL: UI_BASE_URL },
    },
    {
      name: "setup:ops",
      testMatch: /auth\.setup\.ts/,
      use: { baseURL: OPS_BASE_URL },
    },
    {
      name: "setup:client",
      testMatch: /auth\.setup\.ts/,
      use: { baseURL: CLIENT_BASE_URL },
    },

    /* ----------------------------------------------------------------- */
    /* Smoke suites — one per UI.                                        */
    /* ----------------------------------------------------------------- */
    {
      name: "desk-ui",
      testMatch: /desk-ui\.smoke\.spec\.ts/,
      dependencies: ["setup:desk"],
      use: {
        ...devices["Desktop Chrome"],
        baseURL: UI_BASE_URL,
        storageState: DESK_STORAGE,
      },
    },
    {
      name: "ops-ui",
      testMatch: /ops-ui\.smoke\.spec\.ts/,
      dependencies: ["setup:ops"],
      use: {
        ...devices["Desktop Chrome"],
        baseURL: OPS_BASE_URL,
        storageState: OPS_STORAGE,
      },
    },
    {
      name: "client-ui",
      testMatch: /client-ui\.smoke\.spec\.ts/,
      dependencies: ["setup:client"],
      use: {
        ...devices["Desktop Chrome"],
        baseURL: CLIENT_BASE_URL,
        storageState: CLIENT_STORAGE,
      },
    },
  ],

  /*
   * We intentionally do NOT start the UI servers from Playwright. The app
   * graph (Next.js apps + Keycloak + FastAPI + Postgres + Kafka + Redis)
   * is orchestrated by `make up-all` and is too fragile to lifecycle from
   * the test runner. To enable autostart, uncomment and tune below.
   *
   * webServer: [
   *   {
   *     command: "pnpm --filter ui dev",
   *     url: UI_BASE_URL,
   *     reuseExistingServer: !CI,
   *     timeout: 120_000,
   *   },
   *   {
   *     command: "pnpm --filter ops-ui dev",
   *     url: OPS_BASE_URL,
   *     reuseExistingServer: !CI,
   *     timeout: 120_000,
   *   },
   *   {
   *     command: "pnpm --filter client-ui dev",
   *     url: CLIENT_BASE_URL,
   *     reuseExistingServer: !CI,
   *     timeout: 120_000,
   *   },
   * ],
   */
});
