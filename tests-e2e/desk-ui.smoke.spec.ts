import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * desk-ui smoke test — critical path: login + view portfolio.
 *
 * Preconditions:
 *   - desk UI running at UI_BASE_URL (default http://localhost:3000)
 *   - Keycloak + FastAPI + Postgres running (make up-all)
 *   - auth.setup.ts has saved tests-e2e/.auth/desk.json with a logged-in session
 *
 * If the storageState is empty (no E2E_TEST_USER provided), the authed steps
 * are skipped but we still run the unauthenticated redirect-to-login check so
 * the smoke suite catches gross regressions.
 */

const STORAGE_PATH = path.join(__dirname, ".auth", "desk.json");

function hasAuthSession(): boolean {
  try {
    const raw = fs.readFileSync(STORAGE_PATH, "utf-8");
    const parsed = JSON.parse(raw) as { cookies?: unknown[] };
    return Array.isArray(parsed.cookies) && parsed.cookies.length > 0;
  } catch {
    return false;
  }
}

test.describe("desk-ui smoke", () => {
  test("unauthenticated root redirects to /login", async ({ browser }) => {
    // Fresh context with no storage state — proves the auth middleware works.
    const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: /mini hedge fund desk/i })).toBeVisible();
    await ctx.close();
  });

  test("authenticated user lands on a fund dashboard and can open the portfolio list", async ({
    page,
  }) => {
    test.skip(
      !hasAuthSession(),
      "No auth session — set E2E_TEST_USER / E2E_TEST_PASSWORD and run test:e2e:setup first.",
    );

    // Landing on "/" should route the session through to a fund dashboard
    // (desk app chooses a default fund and redirects to /[fundSlug]).
    await page.goto("/");
    await expect(page).not.toHaveURL(/\/login/);

    // Fund selector lives in the TopBar of the dashboard layout.
    // It renders either as a <select> (multi-fund) or a <span> with the fund
    // name (single-fund). Either variant counts — we only need to assert the
    // dashboard chrome loaded.
    const fundSelector = page
      .locator("select, span")
      .filter({ hasText: /.+/ })
      .first();
    await expect(fundSelector).toBeVisible();

    // Click the Portfolios nav entry.
    await page.getByRole("link", { name: /portfolios?/i }).first().click();

    // Portfolio list page: look for either a table (loaded) or a skeleton
    // (still loading). Either one proves the route rendered without error.
    await expect(page).toHaveURL(/\/portfolio/);
    await expect(
      page.locator("table, [data-testid='skeleton'], [aria-busy='true']").first(),
    ).toBeVisible({ timeout: 15_000 });
  });
});
