"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "@/shared/lib/api";

interface AuditEntry {
  id: string;
  event_id: string;
  event_type: string;
  actor_id: string | null;
  actor_type: string | null;
  fund_slug: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

interface AuditPage {
  items: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

const PAGE_SIZE = 50;

export default function AuditPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [eventType, setEventType] = useState("");
  const [page, setPage] = useState(0);

  const params = new URLSearchParams();
  if (fundSlug) params.set("fund_slug", fundSlug);
  if (eventType) params.set("event_type", eventType);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(page * PAGE_SIZE));

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "audit", fundSlug, eventType, page],
    queryFn: () => apiFetch<AuditPage>(`admin/audit?${params.toString()}`),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

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
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : data?.items.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">No audit entries found.</p>
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
                <tr key={entry.id} className="border-b border-[var(--border)]">
                  <td className="py-2 text-[var(--muted-foreground)] whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="py-2">
                    <span className="inline-block rounded bg-[var(--muted)] px-2 py-0.5 text-xs font-mono">
                      {entry.event_type}
                    </span>
                  </td>
                  <td className="py-2 text-xs text-[var(--muted-foreground)]">
                    {entry.actor_type}:{entry.actor_id?.slice(0, 8)}
                  </td>
                  <td className="py-2">{entry.fund_slug ?? "-"}</td>
                  <td className="py-2 text-xs text-[var(--muted-foreground)] max-w-xs truncate">
                    {JSON.stringify(entry.payload)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-[var(--muted-foreground)]">
                {data?.total} entries &middot; page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="rounded border border-[var(--border)] px-3 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="rounded border border-[var(--border)] px-3 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
