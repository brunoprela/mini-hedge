"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { cn } from "@/shared/lib/cn";
import { eodHistoryQueryOptions } from "../api";

export function EODHistory({ onSelectDate }: { onSelectDate: (date: string) => void }) {
  const { fundSlug } = useFundContext();
  const { data: history, isLoading } = useQuery(eodHistoryQueryOptions(fundSlug));

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading history...</div>;
  }

  if (!history || history.length === 0) {
    return (
      <div className="rounded-md border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        No EOD runs found. Trigger your first EOD run above.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <Link
          href={`/${fundSlug}/fees`}
          className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] underline-offset-2 hover:underline"
        >
          View Fee Accruals →
        </Link>
      </div>
      <div className="overflow-x-auto rounded-md border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--card)]">
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">Date</th>
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
              Status
            </th>
            <th className="px-3 py-1.5 text-right font-medium text-[var(--muted-foreground)]">
              Steps
            </th>
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
              Started
            </th>
            <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
              Duration
            </th>
          </tr>
        </thead>
        <tbody>
          {history.map((run) => {
            const duration =
              run.started_at && run.completed_at
                ? Math.round(
                    (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) /
                      1000,
                  )
                : null;

            return (
              <tr
                key={run.run_id}
                className="cursor-pointer border-b border-[var(--border)] last:border-0 hover:bg-[var(--sidebar-active)]"
                onClick={() => onSelectDate(run.business_date)}
              >
                <td className="px-3 py-1.5 font-medium">{run.business_date}</td>
                <td className="px-3 py-1.5">
                  <span
                    className={cn(
                      "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                      run.is_successful
                        ? "bg-emerald-400/20 text-emerald-400"
                        : "bg-red-400/20 text-red-400",
                    )}
                  >
                    {run.is_successful ? "Success" : "Failed"}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums">
                  {run.steps_completed}/{run.steps_total}
                </td>
                <td className="px-3 py-1.5 text-[var(--muted-foreground)]">
                  {run.started_at ? new Date(run.started_at).toLocaleTimeString(undefined, { timeZoneName: "short" }) : "--"}
                </td>
                <td className="px-3 py-1.5 text-[var(--muted-foreground)]">
                  {duration !== null ? `${duration}s` : "--"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    </div>
  );
}
