"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { ErrorState } from "@mini-hedge/ui";
import { StatusBadge } from "@mini-hedge/ui";
import { TableSkeleton } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";
import { eventCategory } from "@/shared/lib/audit-utils";

function ExpandablePayload({ payload }: { payload: unknown }) {
  const [open, setOpen] = useState(false);

  if (!payload) return <span className="text-[var(--muted-foreground)]">--</span>;

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-xs font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        {open ? "Hide" : "Show"} payload
      </button>
      {open && (
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-[var(--muted)] p-2 text-[11px] font-mono whitespace-pre-wrap">
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function ChangeHistoryPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [eventFilter, setEventFilter] = useState("");

  const enabled = !!fundSlug;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["change-history", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/audit", {
        params: { query: { limit: 50, fund_slug: fundSlug } },
      });
      if (error) throw error;
      return data;
    },
    enabled,
  });

  const filtered = eventFilter
    ? data?.items.filter((e) =>
        e.event_type.toLowerCase().includes(eventFilter.toLowerCase()),
      )
    : data?.items;

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Change History</h2>

      <div className="mb-6">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
          showPortfolio={false}
        />
      </div>

      {!fundSlug && (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund to view change history.
        </p>
      )}

      {fundSlug && (
        <div className="mb-4">
          <input
            placeholder="Filter by event type"
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
          />
        </div>
      )}

      {fundSlug && isLoading && <TableSkeleton rows={8} columns={5} />}

      {fundSlug && isError && (
        <ErrorState message={error.message} onRetry={refetch} />
      )}

      {fundSlug && !isLoading && !isError && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border)]">
            <thead>
              <tr>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Event Type</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actor</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fund</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Timestamp</th>
                <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {filtered?.map((entry) => (
                <tr key={entry.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                  <td className="px-3 py-2 text-sm">
                    <StatusBadge
                      label={entry.event_type}
                      variant={eventCategory(entry.event_type)}
                    />
                  </td>
                  <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">
                    {entry.actor_type ? (
                      <span>
                        <span className="font-medium">{entry.actor_type}</span>
                        {entry.actor_id && (
                          <span className="ml-1 font-mono">{entry.actor_id.slice(0, 8)}</span>
                        )}
                      </span>
                    ) : (
                      "--"
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm">
                    {entry.fund_slug ? (
                      <span className="inline-block rounded bg-[var(--muted)] px-2 py-0.5 text-xs font-mono">
                        {entry.fund_slug}
                      </span>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">--</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm text-[var(--muted-foreground)] whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-sm align-top">
                    <ExpandablePayload payload={entry.payload} />
                  </td>
                </tr>
              ))}
              {filtered?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                    No audit entries found.
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
