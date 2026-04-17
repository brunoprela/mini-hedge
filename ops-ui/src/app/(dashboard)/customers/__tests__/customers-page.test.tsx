/**
 * Customers page tests.
 *
 * Covers:
 * 1. Create-customer form validates slug regex (`^[a-z0-9-]+$`) and required
 *    fields.
 * 2. A valid slug + name submits through the mocked api client.
 * 3. The customers table renders rows from the mocked GET response.
 *
 * Uses `useRole` forced to admin so the create button and form are visible.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
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

import CustomersPage from "../page";

describe("CustomersPage", () => {
  beforeEach(() => {
    mockGET.mockReset();
    mockPOST.mockReset();
    mockPATCH.mockReset();

    mockGET.mockResolvedValue({
      data: {
        items: [
          {
            id: "c1",
            slug: "acme-capital",
            name: "Acme Capital",
            customer_type: "direct_fund",
            status: "active",
          },
          {
            id: "c2",
            slug: "beta-admin",
            name: "Beta Administrator",
            customer_type: "fund_administrator",
            status: "inactive",
          },
        ],
        total: 2,
      },
      error: null,
    });
  });

  it("renders table rows from the mocked api response", async () => {
    renderWithProviders(<CustomersPage />);

    await waitFor(() => {
      expect(screen.getByText("Acme Capital")).toBeInTheDocument();
    });
    expect(screen.getByText("Beta Administrator")).toBeInTheDocument();
    expect(screen.getByText("acme-capital")).toBeInTheDocument();
  });

  it("rejects an invalid slug and does not call POST", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomersPage />);

    // Open create form
    await user.click(screen.getByRole("button", { name: /create customer/i }));

    // Invalid slug (contains uppercase + space)
    await user.type(screen.getByPlaceholderText(/acme-capital/i), "Acme Capital");
    await user.type(screen.getByPlaceholderText(/^Name$/i), "Acme");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/slug must be lowercase letters/i),
      ).toBeInTheDocument();
    });

    expect(mockPOST).not.toHaveBeenCalled();
  });

  it("submits a valid create-customer payload", async () => {
    const user = userEvent.setup();
    mockPOST.mockResolvedValue({
      data: {
        id: "c3",
        slug: "gamma-fund",
        name: "Gamma Fund",
        customer_type: "direct_fund",
        status: "active",
      },
      error: null,
    });

    renderWithProviders(<CustomersPage />);

    await user.click(screen.getByRole("button", { name: /create customer/i }));
    await user.type(screen.getByPlaceholderText(/acme-capital/i), "gamma-fund");
    await user.type(screen.getByPlaceholderText(/^Name$/i), "Gamma Fund");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(mockPOST).toHaveBeenCalledTimes(1);
    });

    expect(mockPOST).toHaveBeenCalledWith("/api/v1/admin/customers", {
      body: {
        slug: "gamma-fund",
        name: "Gamma Fund",
        customer_type: "direct_fund",
      },
    });
  });
});
