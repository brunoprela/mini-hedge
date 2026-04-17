import { test as setup, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

/**
 * One-time login against each UI's Keycloak realm.
 *
 * Flow (for each UI project):
 *   1. Navigate to "/" — middleware redirects to /login.
 *   2. Click the "Sign in" button, which kicks off the OIDC redirect to Keycloak.
 *   3. Fill the Keycloak form with E2E_TEST_USER / E2E_TEST_PASSWORD.
 *   4. Keycloak redirects back to the app with a session cookie set.
 *   5. Persist storageState so the smoke specs can reuse the session.
 *
 * The test user must exist in each realm (minihedge, minihedge-ops) with the
 * correct role mappings. See tests-e2e/README.md for provisioning notes.
 *
 * IMPORTANT: this setup is skipped unless E2E_TEST_USER and E2E_TEST_PASSWORD
 * are both set. Without them we still write an empty storageState so the
 * dependent smoke specs can run — they'll skip the auth-guarded cases.
 */

const AUTH_DIR = path.join(__dirname, ".auth");

function storageFileForBaseURL(baseURL: string | undefined): string {
  if (!baseURL) throw new Error("baseURL is required on the setup project");
  if (baseURL.includes(":3000")) return path.join(AUTH_DIR, "desk.json");
  if (baseURL.includes(":3100")) return path.join(AUTH_DIR, "ops.json");
  if (baseURL.includes(":3200")) return path.join(AUTH_DIR, "client.json");
  // Fallback — hash the URL so unexpected base URLs still get a stable file.
  return path.join(AUTH_DIR, `${encodeURIComponent(baseURL)}.json`);
}

setup.beforeAll(() => {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
});

setup("authenticate", async ({ page, baseURL }) => {
  const storagePath = storageFileForBaseURL(baseURL);

  const user = process.env.E2E_TEST_USER;
  const password = process.env.E2E_TEST_PASSWORD;

  if (!user || !password) {
    // Write an empty storage state so the dependent smoke project can still
    // load its `use.storageState` without erroring. Auth-dependent specs
    // will skip themselves via `test.skip` (see smoke specs).
    setup.info().annotations.push({
      type: "skip-reason",
      description:
        "E2E_TEST_USER / E2E_TEST_PASSWORD not set — writing empty storageState. " +
        "Auth-gated steps in smoke specs will be skipped.",
    });
    fs.writeFileSync(
      storagePath,
      JSON.stringify({ cookies: [], origins: [] }, null, 2),
    );
    setup.skip(true, "No E2E credentials provided — empty storageState written.");
    return;
  }

  // 1. Landing on "/" should bounce us to /login.
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);

  // 2. Kick off the SSO redirect. All three UIs use the same button copy
  //    variants — match loosely.
  await page.getByRole("button", { name: /sign in/i }).click();

  // 3. We should land on Keycloak. The exact host/realm varies per UI, but
  //    the form fields are consistent.
  await page.waitForURL(/\/realms\/.*\/protocol\/openid-connect/);
  await page.getByLabel(/username/i).fill(user);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /sign in|log in/i }).click();

  // 4. Wait to be back on the app (not on Keycloak or /login).
  await page.waitForURL(
    (url) =>
      !url.pathname.startsWith("/login") &&
      !url.hostname.includes("keycloak") &&
      !url.pathname.includes("/realms/"),
    { timeout: 30_000 },
  );

  // 5. Persist the session.
  await page.context().storageState({ path: storagePath });
});
