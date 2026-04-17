/**
 * Redeem wizard — exercises the gate-warning banner on the Review step.
 *
 * With gate_pct=0.10 (10%) and current_capital=100000, a partial redemption
 * of 50000 (>10% of capital) should surface the "Possible gate" warning on
 * step 2 once the user clicks Continue.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";

const mockUseFunds = vi.fn();
const mockUseInvestorContext = vi.fn();

// URL-tracking next/navigation stub — see subscribe-page.test.tsx for notes.
vi.mock("next/navigation", async () => {
  const { useState, useCallback } = await import("react");
  let currentSearch = "";
  const listeners = new Set<() => void>();
  const router = {
    push: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
    replace: (url: string) => {
      const q = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
      currentSearch = q;
      for (const fn of listeners) fn();
    },
  };
  return {
    useRouter: () => router,
    usePathname: () => "/redeem",
    useSearchParams: () => {
      const [, set] = useState(0);
      const sub = useCallback(() => set((n) => n + 1), []);
      listeners.add(sub);
      return new URLSearchParams(currentSearch);
    },
    useParams: () => ({}),
    redirect: vi.fn(),
    notFound: vi.fn(),
  };
});

vi.mock("@/shared/components/fund-selector", () => ({
  useFunds: () => mockUseFunds(),
  FundSelector: () => null,
}));

vi.mock("@/shared/lib/use-investor-context", () => ({
  useInvestorContext: (fundSlug: string | null) => mockUseInvestorContext(fundSlug),
}));

vi.mock("@/shared/lib/api-client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn() },
  fundHeaders: (slug: string) => ({ "X-Fund-Slug": slug }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import RedeemPage from "../page";

describe("RedeemPage wizard", () => {
  beforeEach(() => {
    mockUseFunds.mockReturnValue({
      data: {
        items: [
          { slug: "alpha", name: "Alpha Fund", base_currency: "USD" },
        ],
      },
      isLoading: false,
      error: null,
    });
    mockUseInvestorContext.mockReturnValue({
      data: {
        investor: { id: "inv-1", name: "Investor One" },
        accounts: [],
        fundTerms: [],
        primaryAccount: {
          share_class: "default",
          ending_capital: "100000",
          shares_held: "1000",
        },
        primaryTerms: {
          share_class: "default",
          minimum_subscription: "10000",
          minimum_redemption: "1000",
          lock_up_months: 0,
          notice_period_days: 30,
          redemption_frequency: "monthly",
          gate_pct: "0.10",
        },
        navPerShare: 100,
      },
      isLoading: false,
    });
  });

  it("shows the gate warning on Review when amount exceeds gate_pct of capital", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /amount/i })).toBeInTheDocument();
    });

    // Enter a partial redemption amount = 50,000 (50% of 100k capital,
    // well above the 10% gate).
    const amountInput = screen.getByPlaceholderText("500000");
    await user.type(amountInput, "50000");

    const continueBtn = screen.getByRole("button", { name: /continue/i });
    await waitFor(() => expect(continueBtn).not.toBeDisabled());
    await user.click(continueBtn);

    // On Review step, the gate warning should be visible.
    await waitFor(() => {
      expect(screen.getByText(/possible gate/i)).toBeInTheDocument();
    });
  });
});
