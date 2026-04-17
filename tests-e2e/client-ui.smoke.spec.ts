import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * client-ui smoke test — critical path: login + view fund detail + open
 * the subscribe wizard.
 *
 * Preconditions:
 *   - client UI running at CLIENT_BASE_URL (default http://localhost:3200)
 *   - Keycloak realm `minihedge` seeded with the E2E_TEST_USER, and that user
 *     must have at least one capital account (so /funds shows a row to click)
 *   - auth.setup.ts has saved tests-e2e/.auth/client.json
 */

const STORAGE_PATH = path.join(__dirname, ".auth", "client.json");

function hasAuthSession(): boolean {
  try {
    const raw = fs.readFileSync(STORAGE_PATH, "utf-8");
    const parsed = JSON.parse(raw) as { cookies?: unknown[] };
    return Array.isArray(parsed.cookies) && parsed.cookies.length > 0;
  } catch {
    return false;
  }
}

test.describe("client-ui smoke", () => {
  test("unauthenticated root redirects to /login", async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: /investor portal/i })).toBeVisible();
    await ctx.close();
  });

  test("investor can open a fund and launch the subscribe wizard", async ({ page }) => {
    test.skip(
      !hasAuthSession(),
      "No auth session — set E2E_TEST_USER / E2E_TEST_PASSWORD and run test:e2e:setup first.",
    );

    // My Funds list.
    await page.goto("/funds");
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: /my funds/i })).toBeVisible();

    // First fund row is a link into /funds/[slug]. The page renders either
    // one real link (if the investor has accounts) or a skeleton. If no
    // link appears, skip the rest of the path — the smoke suite is for
    // critical-path regressions, not data fixtures.
    const firstFundLink = page.locator("table a[href^='/funds/']").first();
    if ((await firstFundLink.count()) === 0) {
      test.skip(true, "Test user has no funds in this environment.");
    }
    await firstFundLink.click();

    // Fund detail page.
    await expect(page).toHaveURL(/\/funds\/[^/]+$/);
    await expect(page.getByRole("heading", { name: /fund detail/i })).toBeVisible();

    // Click Subscribe (it's a <Link>, shown as a button visually).
    await page.getByRole("link", { name: /^subscribe$/i }).first().click();

    // Wizard step 1 shows the Amount heading and a numeric input field
    // labelled "Amount (USD)".
    await expect(page).toHaveURL(/\/subscribe/);
    await expect(page.getByRole("heading", { name: /^amount$/i })).toBeVisible();
    await expect(page.getByLabel(/amount \(usd\)/i)).toBeVisible();
  });
});
