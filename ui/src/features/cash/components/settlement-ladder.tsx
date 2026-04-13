"use client";

import { useQuery } from "@tanstack/react-query";
import { useInstruments } from "@/features/instruments";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatDate } from "@/shared/lib/formatters";
import { settlementLadderQueryOptions, settlementsQueryOptions } from "../api";
import { SettlementGantt, recordsToEvents } from "./settlement-gantt";

function fmtCurrency(value: string): string {
  return Number(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function flowColorClass(value: string): string {
  const n = Number(value);
  if (n > 0) return "text-[var(--success)]";
  if (n < 0) return "text-[var(--destructive)]";
  return "";
}

export function SettlementLadder({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(settlementLadderQueryOptions(fundSlug, portfolioId));
  const { data: settlements } = useQuery(settlementsQueryOptions(fundSlug, portfolioId));
  const { data: instruments } = useInstruments();

  if (isLoading || !data) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">Loading settlement ladder...</div>
    );
  }

  // Build instrument lookup map for Gantt labels
  const instrumentMap = new Map<string, string>();
  if (instruments) {
    for (const inst of instruments) {
      instrumentMap.set(inst.id, inst.ticker);
    }
  }

  // Convert settlement records to Gantt events
  const ganttEvents = settlements ? recordsToEvents(settlements, instrumentMap) : [];

  return (
    <div className="space-y-4">
      {/* Gantt timeline visualization */}
      {ganttEvents.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
            Timeline
          </h3>
          <SettlementGantt events={ganttEvents} />
        </div>
      )}

      {/* Table view */}
      {data.entries.length === 0 ? (
        <div className="text-sm text-[var(--muted-foreground)]">No upcoming settlements.</div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted-foreground)]/5">
                <th className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)]">
                  Date
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
                  Expected Inflow
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
                  Expected Outflow
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
                  Net Flow
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium text-[var(--muted-foreground)]">
                  Cumulative Balance
                </th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((entry) => (
                <tr
                  key={`${entry.settlement_date}-${entry.currency}`}
                  className="border-b border-[var(--border)] last:border-b-0"
                >
                  <td className="px-3 py-2 text-left">{formatDate(entry.settlement_date)}</td>
                  <td className="px-3 py-2 text-right font-mono text-[var(--success)]">
                    {fmtCurrency(entry.expected_inflow)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-[var(--destructive)]">
                    {fmtCurrency(entry.expected_outflow)}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono ${flowColorClass(entry.net_flow)}`}>
                    {fmtCurrency(entry.net_flow)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">
                    {fmtCurrency(entry.cumulative_balance)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
