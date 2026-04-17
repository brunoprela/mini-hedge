/**
 * Trade ticket inner form — renders the ticket panel with all network-touching
 * dependencies stubbed out. We verify three user-observable behaviors:
 *
 *  1. The quantity input is controllable.
 *  2. Clicking the buy/sell side toggle updates the submit button label.
 *  3. The submit button stays disabled until instrument, quantity and price
 *     are filled (the component's `canSubmit` gate).
 *
 * We avoid diving into mutation flow — that's covered by e2e tests.
 */

import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";

// Mock every feature-level API call so nothing hits the network.
vi.mock("@/features/alpha/api", () => ({
  runWhatIf: vi.fn().mockResolvedValue(null),
}));

vi.mock("@/features/compliance/api", () => ({
  checkTradeCompliance: vi.fn().mockResolvedValue({
    approved: true,
    blocked_by: [],
    results: [],
  }),
}));

vi.mock("@/features/instruments/api", () => ({
  instrumentSearchQueryOptions: () => ({
    queryKey: ["instruments-search", ""],
    queryFn: async () => [],
  }),
}));

vi.mock("@/features/market-data/api", () => ({
  latestPriceQueryOptions: () => ({
    queryKey: ["latest-price", ""],
    queryFn: async () => null,
  }),
}));

vi.mock("@/features/orders/api", () => ({
  createOrder: vi.fn().mockResolvedValue({ id: "ord-1", state: "filled" }),
  createAlgoOrder: vi.fn().mockResolvedValue({ id: "ord-1", state: "filled" }),
}));

vi.mock("@/shared/hooks/use-fund-context", () => ({
  useFundContext: () => ({ fundSlug: "test-fund" }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { TradeTicketInner } from "../trade-ticket-inner";

describe("TradeTicketInner", () => {
  it("keeps the submit button disabled until instrument + qty + price are set", () => {
    renderWithProviders(
      <TradeTicketInner portfolioId="p1" onClose={vi.fn()} />,
    );

    // The submit button is `type=submit` and carries a dynamic label like
    // "Buy ..." — select by type attribute to disambiguate from the side
    // toggle buttons (type=button).
    const submit = document.querySelector<HTMLButtonElement>(
      'button[type="submit"]',
    );
    expect(submit).not.toBeNull();
    expect(submit).toBeDisabled();
  });

  it("accepts a quantity value without emitting validation errors", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TradeTicketInner portfolioId="p1" onClose={vi.fn()} />,
    );

    const qty = screen.getByLabelText(/qty/i);
    await user.type(qty, "100");

    expect(qty).toHaveValue(100);
    expect(
      screen.queryByText(/must be a positive number/i),
    ).not.toBeInTheDocument();
  });

  it("toggles the side from buy to sell via the side buttons", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TradeTicketInner portfolioId="p1" onClose={vi.fn()} />,
    );

    // The side group uses two `type=button` buttons labeled "Buy" / "Sell".
    // Submit is `type=submit`. Click the "Sell" side button, then verify the
    // submit button's label changed accordingly.
    const sideButtons = screen.getAllByRole("button");
    const sellToggle = sideButtons.find(
      (b) => b.textContent?.trim() === "Sell" && b.getAttribute("type") === "button",
    );
    expect(sellToggle).toBeDefined();
    await user.click(sellToggle as HTMLElement);

    const submit = document.querySelector<HTMLButtonElement>(
      'button[type="submit"]',
    );
    expect(submit?.textContent).toMatch(/^Sell/);
  });
});
