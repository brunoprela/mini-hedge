"use client";

import { useQuery } from "@tanstack/react-query";
import { ErrorState, TableSkeleton } from "@mini-hedge/ui";
import { PayloadCell } from "@/shared/components/payload-cell";
import { StatusBadge } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";

export default function SignOffPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["sign-off"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/audit", {
        params: { query: { event_type: "SIGN_OFF", limit: 50 } },
      });
      if (error) throw error;
      return data;
    },
  });

  const rows = data?.items ?? [];

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Sign-Off Records</h2>

      {isLoading && <TableSkeleton rows={6} columns={5} />}

      {isError && <ErrorState message={error.message} onRetry={refetch} />}

      {!isLoading && !isError && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border)]">
            <thead>
              <tr>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actor</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Entity</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Event Type</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {rows.map((entry) => (
                <tr
                  key={entry.id}
                  className="transition-colors hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)] whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-sm">
                    {entry.actor_id ? (
                      <span className="font-mono text-xs">
                        {entry.actor_id.slice(0, 8)}
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
                      <span className="text-[var(--muted-foreground)]">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm">
                    <StatusBadge label={entry.event_type} variant="neutral" />
                  </td>
                  <td className="px-3 py-2 text-sm">
                    <PayloadCell payload={entry.payload} />
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]"
                  >
                    No sign-off records found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
