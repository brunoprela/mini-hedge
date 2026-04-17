"use client";

import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ErrorState, TableSkeleton } from "@mini-hedge/ui";
import { StatusBadge } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";
import type { CustomerInfo } from "@/shared/types";

export default function ClientSwitcherPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["client-switcher"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/customers", {
        params: { query: { limit: 100 } },
      });
      if (error) throw error;
      return data;
    },
  });

  const rows = data?.items ?? [];
  const activeCount = rows.filter((c) => c.status === "active").length;
  const faCount = rows.filter(
    (c) => c.customer_type === "fund_administrator",
  ).length;

  function handleSwitch(customer: CustomerInfo) {
    toast.success(`Switched to ${customer.name}`);
  }

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Client Switcher</h2>

      {isLoading && <TableSkeleton rows={6} columns={5} />}

      {isError && <ErrorState message={error.message} onRetry={refetch} />}

      {!isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-3">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Customers
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {rows.length}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Active
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {activeCount}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Fund Administrators
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {faCount}
              </dd>
            </div>
          </dl>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Name</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Slug</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Type</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className="transition-colors hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-2 text-sm font-medium">
                      {row.name}
                    </td>
                    <td className="px-3 py-2 text-sm font-mono">
                      {row.slug}
                    </td>
                    <td className="px-3 py-2 text-sm">{row.customer_type}</td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={row.status}
                        variant={
                          row.status === "active" ? "success" : "neutral"
                        }
                      />
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <button
                        type="button"
                        onClick={() => handleSwitch(row)}
                        className="rounded bg-[var(--primary)] px-2 py-1 text-xs text-white hover:opacity-90"
                      >
                        Switch to
                      </button>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]"
                    >
                      No customers found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
