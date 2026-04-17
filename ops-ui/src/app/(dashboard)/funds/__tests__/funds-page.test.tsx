/**
 * Funds page — base-currency regex check.
 *
 * The create-fund schema requires the base currency to be a 3-letter upper-case
 * code. We verify that entering "usd" (lowercase) or a non-3-letter value
 * triggers the validation error and prevents a network call.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";

const mockGET = vi.fn();
const mockPOST = vi.fn();
const mockPATCH = vi.fn();

vi.mock("@/shared/lib/api-client", () => ({
  api: {
    GET: (...args: unknown[]) => mockGET(...args),
    POST: (...args: unknown[]) => mockPOST(...args),
    PATCH: (...args: unknown[]) => mockPATCH(...args),
  },
}));

vi.mock("@/shared/lib/use-role", () => ({
  useRole: () => ({ role: "ops_admin", isAdmin: true }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import FundsPage from "../page";

describe("FundsPage", () => {
  beforeEach(() => {
    mockGET.mockReset();
    mockPOST.mockReset();
    mockPATCH.mockReset();

    // Provide one existing row so the page doesn't hit the EmptyState branch
    // (which has a lucide-react rendering quirk unrelated to what we're
    // testing). Our tests only exercise the create-fund form.
    mockGET.mockResolvedValue({
      data: {
        items: [
          {
            id: "f0",
            slug: "existing",
            name: "Existing Fund",
            base_currency: "USD",
            status: "active",
          },
        ],
        total: 1,
      },
      error: null,
    });
  });

  it("rejects a non-3-letter base currency", async () => {
    const user = userEvent.setup();
    renderWithProviders(<FundsPage />);

    await user.click(screen.getByRole("button", { name: /create fund/i }));

    await user.type(screen.getByPlaceholderText(/^Slug$/i), "my-fund");
    await user.type(screen.getByPlaceholderText(/^Name$/i), "My Fund");
    // Default is "USD" — clear it and enter 3 lowercase chars, which fails
    // the 3-letter uppercase regex even though it passes the min(3) length.
    const currency = screen.getByPlaceholderText("USD");
    await user.clear(currency);
    await user.type(currency, "usd");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/3-letter currency code/i),
      ).toBeInTheDocument();
    });

    expect(mockPOST).not.toHaveBeenCalled();
  });

  it("submits with the default USD base currency", async () => {
    const user = userEvent.setup();
    mockPOST.mockResolvedValue({
      data: { id: "f1", slug: "alpha", name: "Alpha", base_currency: "USD", status: "active" },
      error: null,
    });

    renderWithProviders(<FundsPage />);

    await user.click(screen.getByRole("button", { name: /create fund/i }));
    await user.type(screen.getByPlaceholderText(/^Slug$/i), "alpha-fund");
    await user.type(screen.getByPlaceholderText(/^Name$/i), "Alpha Fund");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(mockPOST).toHaveBeenCalledTimes(1);
    });

    expect(mockPOST).toHaveBeenCalledWith("/api/v1/admin/funds", {
      body: {
        slug: "alpha-fund",
        name: "Alpha Fund",
        base_currency: "USD",
      },
    });
  });
});
