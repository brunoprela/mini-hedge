"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { portfolioTCAQueryOptions } from "../api";
import type { TCAReport } from "../types";

function fmtBps(v: string) {
  const n = parseFloat(v);
  return n.toFixed(2);
}

function fmtCurrency(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function fmtPrice(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function costColor(bps: string) {
  const n = parseFloat(bps);
  if (n <= 2) return "var(--success)";
  if (n <= 5) return "var(--foreground)";
  return "var(--destructive)";
}

export function TCADashboard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: report, isLoading } = useQuery(portfolioTCAQueryOptions(fundSlug, portfolioId));

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading TCA data...</div>;
  }

  if (!report || !report.reports || report.reports.length === 0) return null;

  return (
    <div className="space-y-2">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <SummaryCard label="Avg Total Cost" value={`${fmtBps(report.avg_total_cost_bps)} bps`} />
        <SummaryCard label="Avg Spread Cost" value={`${fmtBps(report.avg_spread_cost_bps)} bps`} />
        <SummaryCard label="Avg Impact Cost" value={`${fmtBps(report.avg_impact_cost_bps)} bps`} />
        <SummaryCard label="Total Cost" value={fmtCurrency(report.total_cost_usd)} />
      </div>

      {/* Reports table */}
      <div className="overflow-x-auto rounded-md border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="px-3 py-2">Instrument</th>
              <th className="px-3 py-2">Side</th>
              <th className="px-3 py-2 text-right">Qty</th>
              <th className="px-3 py-2 text-right">Arrival Price</th>
              <th className="px-3 py-2 text-right">Avg Fill</th>
              <th className="px-3 py-2 text-right">VWAP</th>
              <th className="px-3 py-2 text-right">Spread (bps)</th>
              <th className="px-3 py-2 text-right">Impact (bps)</th>
              <th className="px-3 py-2 text-right">Total Cost (bps)</th>
              <th className="px-3 py-2 text-right">Total Cost ($)</th>
            </tr>
          </thead>
          <tbody>
            {report.reports.map((r: TCAReport) => (
              <tr
                key={r.order_id}
                className="border-b border-[var(--table-border)] hover:bg-[var(--table-row-hover)]"
              >
                <td className="px-3 py-2 font-mono">{r.instrument_id}</td>
                <td className="px-3 py-2">
                  <span
                    className="text-xs font-medium uppercase"
                    style={{
                      color: r.side === "buy" ? "var(--success)" : "var(--destructive)",
                    }}
                  >
                    {r.side}
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono">{fmtPrice(r.quantity)}</td>
                <td className="px-3 py-2 text-right font-mono">{fmtPrice(r.arrival_price)}</td>
                <td className="px-3 py-2 text-right font-mono">{fmtPrice(r.avg_fill_price)}</td>
                <td className="px-3 py-2 text-right font-mono">{fmtPrice(r.vwap)}</td>
                <td
                  className="px-3 py-2 text-right font-mono"
                  style={{ color: costColor(r.spread_cost_bps) }}
                >
                  {fmtBps(r.spread_cost_bps)}
                </td>
                <td
                  className="px-3 py-2 text-right font-mono"
                  style={{ color: costColor(r.impact_cost_bps) }}
                >
                  {fmtBps(r.impact_cost_bps)}
                </td>
                <td
                  className="px-3 py-2 text-right font-mono font-semibold"
                  style={{ color: costColor(r.total_cost_bps) }}
                >
                  {fmtBps(r.total_cost_bps)}
                </td>
                <td className="px-3 py-2 text-right font-mono">{fmtCurrency(r.total_cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold">{value}</p>
    </div>
  );
}
