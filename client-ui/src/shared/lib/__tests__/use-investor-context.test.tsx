/**
 * useInvestorContext — hook-level test.
 *
 * Verifies the hook composes multiple upstream API calls into the documented
 * InvestorContext shape: investor record, accounts, fund terms, and the
 * primary convenience accessors. Each underlying `api.GET` call is mocked
 * per-path to return canned responses.
 */

import { describe, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";
import { renderHookWithProviders } from "@/test/utils";

type GetArgs = [string, unknown?];
const mockGET = vi.fn(async (...args: GetArgs) => {
  const path = args[0];
  if (path === "/api/v1/capital/investors") {
    return {
      data: [{ id: "inv-1", name: "Investor One" }],
      error: null,
    };
  }
  if (path === "/api/v1/capital/investors/{investor_id}/history") {
    return {
      data: [
        {
          share_class: "default",
          ending_capital: "250000",
          shares_held: "2500",
        },
      ],
      error: null,
    };
  }
  if (path === "/api/v1/investor-operations/fund-terms") {
    return {
      data: [
        {
          share_class: "default",
          minimum_subscription: "10000",
          minimum_redemption: "1000",
          lock_up_months: 0,
          notice_period_days: 30,
          redemption_frequency: "monthly",
          gate_pct: "0.10",
        },
      ],
      error: null,
    };
  }
  if (path === "/api/v1/eod/nav/history") {
    return {
      data: [
        { business_date: "2026-04-15", nav_per_share: "101.25" },
        { business_date: "2026-04-16", nav_per_share: "102.50" },
      ],
      error: null,
    };
  }
  return { data: null, error: null };
});

vi.mock("@/shared/lib/api-client", () => ({
  api: { GET: (...args: GetArgs) => mockGET(...args) },
  fundHeaders: (slug: string) => ({ "X-Fund-Slug": slug }),
}));

import { useInvestorContext } from "../use-investor-context";

describe("useInvestorContext", () => {
  it("returns the expected shape when a fund slug is supplied", async () => {
    const { result } = renderHookWithProviders(() => useInvestorContext("alpha"));

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const ctx = result.current.data;
    expect(ctx).toBeDefined();
    expect(ctx?.investor).toEqual({ id: "inv-1", name: "Investor One" });
    expect(ctx?.accounts).toHaveLength(1);
    expect(ctx?.fundTerms).toHaveLength(1);
    expect(ctx?.primaryAccount?.share_class).toBe("default");
    expect(ctx?.primaryTerms?.share_class).toBe("default");
    // NAV per share picks the latest business_date from the mocked history.
    expect(ctx?.navPerShare).toBe(102.5);
  });

  it("stays disabled (no fetch) when fund slug is null", async () => {
    mockGET.mockClear();
    const { result } = renderHookWithProviders(() => useInvestorContext(null));

    // `enabled: false` → query does not fire; data stays undefined.
    expect(result.current.data).toBeUndefined();
    expect(mockGET).not.toHaveBeenCalled();
  });
});
