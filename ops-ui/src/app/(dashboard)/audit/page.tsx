"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@mini-hedge/ui";
import { ErrorState } from "@mini-hedge/ui";
import { TableSkeleton } from "@mini-hedge/ui";
import { Pagination } from "@mini-hedge/ui";
import { PayloadCell } from "@/shared/components/payload-cell";
import { StatusBadge } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";
import { eventCategory } from "@/shared/lib/audit-utils";
import { PAGE_SIZE } from "@/shared/lib/constants";

export default function AuditPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [eventType, setEventType] = useState("");
  const [page, setPage] = useState(0);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "audit", fundSlug, eventType, page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/audit", {
        params: {
          query: {
            fund_slug: fundSlug || undefined,
            event_type: eventType || undefined,
            limit: PAGE_SIZE,
            offset: page * PAGE_SIZE,
          },
        },
      });
      if (error) throw error;
      return data;
    },
  });

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Audit Log</h2>

      <div className="flex gap-3 mb-4">
        <input
          placeholder="Filter by fund slug"
          value={fundSlug}
          onChange={(e) => {
            setFundSlug(e.target.value);
            setPage(0);
          }}
          className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
        />
        <input
          placeholder="Filter by event type"
          value={eventType}
          onChange={(e) => {
            setEventType(e.target.value);
            setPage(0);
          }}
          className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
        />
      </div>

      {isLoading ? (
        <TableSkeleton rows={8} columns={5} />
      ) : isError ? (
        <ErrorState message={error.message} onRetry={refetch} />
      ) : data?.items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No audit entries"
          description="No audit log entries match your filters."
        />
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="py-2 font-medium">Time</th>
                <th className="py-2 font-medium">Event</th>
                <th className="py-2 font-medium">Actor</th>
                <th className="py-2 font-medium">Fund</th>
                <th className="py-2 font-medium">Details</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((entry) => (
                <tr key={entry.id} className="border-b border-[var(--border)] align-top">
                  <td className="py-2 text-[var(--muted-foreground)] whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="py-2">
                    <StatusBadge
                      label={entry.event_type}
                      variant={eventCategory(entry.event_type)}
                    />
                  </td>
                  <td className="py-2 text-xs text-[var(--muted-foreground)]">
                    {entry.actor_type ? (
                      <span>
                        <span className="font-medium">{entry.actor_type}</span>
                        {entry.actor_id && (
                          <span className="ml-1 font-mono">{entry.actor_id.slice(0, 8)}</span>
                        )}
                      </span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="py-2">
                    {entry.fund_slug ? (
                      <span className="inline-block rounded bg-[var(--muted)] px-2 py-0.5 text-xs font-mono">
                        {entry.fund_slug}
                      </span>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">-</span>
                    )}
                  </td>
                  <td className="py-2">
                    <PayloadCell payload={entry.payload} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && (
            <Pagination total={data.total} limit={PAGE_SIZE} page={page} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}
