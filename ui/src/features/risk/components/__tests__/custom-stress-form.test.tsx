/**
 * Custom stress form — verifies the form renders and that clicking "Run" with
 * valid shock rows calls the mutation. Mocks the API call and fund context so
 * the test stays hermetic.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";

const mockRunCustomStressTest = vi.fn().mockResolvedValue({
  scenario_name: "Equity crash",
  total_pnl_impact: "-1500",
  total_pct_change: "-5.00",
  position_impacts: [],
});

vi.mock("../../api", () => ({
  runCustomStressTest: (...args: unknown[]) => mockRunCustomStressTest(...args),
}));

vi.mock("@/shared/hooks/use-fund-context", () => ({
  useFundContext: () => ({ fundSlug: "test-fund" }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { CustomStressForm } from "../custom-stress-form";

describe("CustomStressForm", () => {
  beforeEach(() => {
    mockRunCustomStressTest.mockClear();
  });

  it("renders scenario inputs and at least one shock row", () => {
    renderWithProviders(<CustomStressForm portfolioId="portfolio-1" />);

    expect(screen.getByPlaceholderText(/equity crash/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/factor/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run stress test/i })).toBeInTheDocument();
  });

  it("submits the populated shock to the API when the form is valid", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomStressForm portfolioId="portfolio-1" />);

    await user.type(screen.getByPlaceholderText(/equity crash/i), "Equity crash");
    await user.type(screen.getByPlaceholderText(/factor/i), "SPX");
    await user.type(screen.getByPlaceholderText(/shock/i), "-10");

    await user.click(screen.getByRole("button", { name: /run stress test/i }));

    await waitFor(() => {
      expect(mockRunCustomStressTest).toHaveBeenCalledTimes(1);
    });

    // The second arg is portfolio id, third is the payload
    const call = mockRunCustomStressTest.mock.calls[0];
    expect(call[1]).toBe("portfolio-1");
    expect(call[2]).toMatchObject({
      name: "Equity crash",
      shocks: { SPX: -10 },
    });
  });
});
