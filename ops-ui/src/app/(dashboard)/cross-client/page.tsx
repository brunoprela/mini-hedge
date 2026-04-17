"use client";

import { useQuery } from "@tanstack/react-query";
import { CardSkeleton, ErrorState } from "@mini-hedge/ui";
import { PayloadCell } from "@/shared/components/payload-cell";
import { StatusBadge } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";
import { eventCategory } from "@/shared/lib/audit-utils";

export default function CrossClientPage() {
  const customersQuery = useQuery({
    queryKey: ["cross-client", "customers"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/customers", {
        params: { query: { limit: 100 } },
      });
      if (error) throw error;
      return data;
    },
  });

  const fundsQuery = useQuery({
    queryKey: ["cross-client", "funds"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/funds", {
        params: { query: { limit: 100 } },
      });
      if (error) throw error;
      return data;
    },
  });

  const usersQuery = useQuery({
    queryKey: ["cross-client", "users"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/users", {
        params: { query: { limit: 1 } },
      });
      if (error) throw error;
      return data;
    },
  });

  const auditQuery = useQuery({
    queryKey: ["cross-client", "audit"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/audit", {
        params: { query: { limit: 20 } },
      });
      if (error) throw error;
      return data;
    },
  });

  const isLoading =
    customersQuery.isLoading ||
    fundsQuery.isLoading ||
    usersQuery.isLoading ||
    auditQuery.isLoading;

  const hasError =
    customersQuery.isError ||
    fundsQuery.isError ||
    usersQuery.isError ||
    auditQuery.isError;

  const errorMessage =
    customersQuery.error?.message ||
    fundsQuery.error?.message ||
    usersQuery.error?.message ||
    auditQuery.error?.message ||
    "Unknown error";

  const totalCustomers = customersQuery.data?.items.length ?? 0;
  const totalFunds = fundsQuery.data?.items.length ?? 0;
  const totalUsers = usersQuery.data?.total ?? 0;
  const auditEntries = auditQuery.data?.items ?? [];

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Cross-Client Dashboard</h2>

      {isLoading && <CardSkeleton count={4} />}

      {hasError && (
        <ErrorState
          message={errorMessage}
          onRetry={() => {
            customersQuery.refetch();
            fundsQuery.refetch();
            usersQuery.refetch();
            auditQuery.refetch();
          }}
        />
      )}

      {!isLoading && !hasError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-4">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Customers
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {totalCustomers}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Funds
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {totalFunds}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Users
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {totalUsers}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Active Operators
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                —
              </dd>
            </div>
          </dl>

          {/* Recent audit activity */}
          <h3 className="mb-3 text-sm font-medium text-[var(--foreground)]">
            Recent Activity
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Time</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Event</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actor</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fund</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {auditEntries.map((entry) => (
                  <tr
                    key={entry.id}
                    className="transition-colors hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)] whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={entry.event_type}
                        variant={eventCategory(entry.event_type)}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm text-xs text-[var(--muted-foreground)]">
                      {entry.actor_type ? (
                        <span>
                          <span className="font-medium">
                            {entry.actor_type}
                          </span>
                          {entry.actor_id && (
                            <span className="ml-1 font-mono">
                              {entry.actor_id.slice(0, 8)}
                            </span>
                          )}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      {entry.fund_slug ? (
                        <span className="inline-block rounded bg-[var(--muted)] px-2 py-0.5 text-xs font-mono">
                          {entry.fund_slug}
                        </span>
                      ) : (
                        <span className="text-[var(--muted-foreground)]">
                          —
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <PayloadCell payload={entry.payload} />
                    </td>
                  </tr>
                ))}
                {auditEntries.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]"
                    >
                      No recent activity.
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
