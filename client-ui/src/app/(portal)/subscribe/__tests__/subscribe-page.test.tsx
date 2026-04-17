/**
 * Subscribe wizard — step-1 amount validation and step navigation.
 *
 * We stub the supporting hooks (`useFunds`, `useInvestorContext`) with fixed
 * data so the wizard renders synchronously, then drive the form via
 * userEvent to check:
 *   - Invalid amount (0) keeps the Continue button disabled.
 *   - Valid amount enables Continue, which advances to step 2.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";

const mockUseFunds = vi.fn();
const mockUseInvestorContext = vi.fn();

// Override the default next/navigation mock with one that actually tracks
// search-param updates, so wizard step changes (driven by router.replace) are
// reflected in useSearchParams on the next render.
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
    usePathname: () => "/subscribe",
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

import SubscribePage from "../page";

describe("SubscribePage wizard", () => {
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
        primaryAccount: { share_class: "default", ending_capital: "1000000", shares_held: "1000" },
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

  it("keeps Continue disabled when amount is zero", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SubscribePage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /amount/i })).toBeInTheDocument();
    });

    const amountInput = screen.getByPlaceholderText("1,000,000");
    await user.type(amountInput, "0");

    const continueBtn = screen.getByRole("button", { name: /continue/i });
    expect(continueBtn).toBeDisabled();
  });

  it("navigates from step 1 → step 2 once a valid amount is entered", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SubscribePage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /amount/i })).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("1,000,000"), "50000");

    const continueBtn = screen.getByRole("button", { name: /continue/i });
    await waitFor(() => expect(continueBtn).not.toBeDisabled());
    await user.click(continueBtn);

    // Step 2 heading is "Review"
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /review/i })).toBeInTheDocument();
    });
  });
});
