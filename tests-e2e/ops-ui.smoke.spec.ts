import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * ops-ui smoke test — critical path: login + view customers.
 *
 * Preconditions:
 *   - ops UI running at OPS_BASE_URL (default http://localhost:3100)
 *   - Keycloak realm `minihedge-ops` seeded with the E2E_TEST_USER
 *   - auth.setup.ts has saved tests-e2e/.auth/ops.json
 */

const STORAGE_PATH = path.join(__dirname, ".auth", "ops.json");

function hasAuthSession(): boolean {
  try {
    const raw = fs.readFileSync(STORAGE_PATH, "utf-8");
    const parsed = JSON.parse(raw) as { cookies?: unknown[] };
    return Array.isArray(parsed.cookies) && parsed.cookies.length > 0;
  } catch {
    return false;
  }
}

test.describe("ops-ui smoke", () => {
  test("unauthenticated root redirects to /login", async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: /ops console/i })).toBeVisible();
    await ctx.close();
  });

  test("authenticated user can navigate to the Customers list", async ({ page }) => {
    test.skip(
      !hasAuthSession(),
      "No auth session — set E2E_TEST_USER / E2E_TEST_PASSWORD and run test:e2e:setup first.",
    );

    await page.goto("/");
    await expect(page).not.toHaveURL(/\/login/);

    // Sidebar link to Customers.
    await page.getByRole("link", { name: /customers/i }).first().click();

    await expect(page).toHaveURL(/\/customers/);

    // Heading is rendered by the customers page once data loads.
    await expect(page.getByRole("heading", { name: /customers/i })).toBeVisible({
      timeout: 15_000,
    });

    // Either a data table or a skeleton must be present.
    await expect(
      page.locator("table, [data-testid='skeleton'], [aria-busy='true']").first(),
    ).toBeVisible({ timeout: 15_000 });
  });
});
