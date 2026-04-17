/**
 * Block allocation form — validates that the sum-to-100% rule fires when the
 * user tries to submit with legs that don't sum to 100. Mocks:
 *  - `createBlockAllocation` so we never hit the network
 *  - `portfoliosQueryOptions` so the <select> is populated deterministically
 *  - `useFundContext` so we don't need a real Next.js router in the tree
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";

const mockCreateBlockAllocation = vi.fn().mockResolvedValue({ id: "alloc-1" });

vi.mock("@/features/orders/api", () => ({
  createBlockAllocation: (...args: unknown[]) => mockCreateBlockAllocation(...args),
}));

vi.mock("@/features/portfolio/api", () => ({
  portfoliosQueryOptions: () => ({
    queryKey: ["portfolios", "test-fund"],
    queryFn: async () => [
      { id: "p1", name: "Portfolio One" },
      { id: "p2", name: "Portfolio Two" },
    ],
  }),
}));

vi.mock("@/shared/hooks/use-fund-context", () => ({
  useFundContext: () => ({ fundSlug: "test-fund" }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { BlockAllocationDialog } from "../block-allocation-dialog";

describe("BlockAllocationDialog", () => {
  beforeEach(() => {
    mockCreateBlockAllocation.mockClear();
  });

  it("shows a validation error when legs do not sum to 100%", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BlockAllocationDialog open onClose={vi.fn()} />);

    // Fill in instrument, total quantity
    await user.type(screen.getByPlaceholderText(/e\.g\. AAPL/i), "AAPL");
    await user.type(screen.getByPlaceholderText("0"), "1000");

    // Wait for portfolios query to resolve and populate the select
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Portfolio One" })).toBeInTheDocument();
    });

    // Pick portfolio for leg 1 (the select that has "Select portfolio" option)
    const portfolioSelect = screen
      .getByRole("option", { name: "Select portfolio" })
      .closest("select") as HTMLSelectElement;
    await user.selectOptions(portfolioSelect, "p1");

    const pctInput = screen.getByPlaceholderText("%");
    await user.type(pctInput, "60");

    // Submit; sum != 100 should block the mutation and render a running total.
    await user.click(screen.getByRole("button", { name: /create allocation/i }));

    // The "Current total: X%" hint renders when the sum != 100, confirming
    // the running-sum calculation is wired up. Either the formal zod error
    // or this hint demonstrates the validation gate is in effect.
    await waitFor(() => {
      expect(screen.getByText(/current total:/i)).toBeInTheDocument();
    });

    // The mutation must not have fired because validation failed.
    expect(mockCreateBlockAllocation).not.toHaveBeenCalled();
  });

  it("adds a new leg row when the user clicks 'Add Portfolio'", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BlockAllocationDialog open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Portfolio One" })).toBeInTheDocument();
    });

    // Starts with one leg
    expect(screen.getAllByPlaceholderText("%")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: /add portfolio/i }));

    // Now has two legs
    expect(screen.getAllByPlaceholderText("%")).toHaveLength(2);
  });
});
