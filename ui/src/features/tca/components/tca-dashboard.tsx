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

  if (!report?.orders || report.orders.length === 0) return null;

  return (
    <div className="space-y-2">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <SummaryCard label="Avg Total Cost" value={`${fmtBps(report.avg_total_cost_bps)} bps`} />
        <SummaryCard label="Avg Spread Cost" value={`${fmtBps(report.avg_spread_bps)} bps`} />
        <SummaryCard label="Avg Impact Cost" value={`${fmtBps(report.avg_impact_bps)} bps`} />
        <SummaryCard label="Total Cost" value={fmtCurrency(report.total_cost_usd)} />
      </div>

      {/* Reports table */}
      <div className="overflow-x-auto rounded-md border border-[var(--border)]">
        <table className="min-w-full divide-y divide-[var(--border)] text-sm">
          <thead>
            <tr className="text-left text-xs text-[var(--muted-foreground)]">
              <th scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">Instrument</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">Side</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Qty</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Arrival Price</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Avg Fill</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">VWAP</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Spread (bps)</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Impact (bps)</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Total Cost (bps)</th>
              <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Total Cost ($)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {report.orders.map((r: TCAReport) => (
              <tr
                key={r.order_id}
                className="hover:bg-[var(--table-row-hover)]"
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
                <td className="px-3 py-2 text-right font-mono">{fmtPrice(r.arrival_mid_price)}</td>
                <td className="px-3 py-2 text-right font-mono">
                  {r.avg_fill_price ? fmtPrice(r.avg_fill_price) : "-"}
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  {r.vwap_benchmark ? fmtPrice(r.vwap_benchmark) : "-"}
                </td>
                <td
                  className="px-3 py-2 text-right font-mono"
                  style={{ color: costColor(r.spread_cost_bps) }}
                >
                  {fmtBps(r.spread_cost_bps)}
                </td>
                <td
                  className="px-3 py-2 text-right font-mono"
                  style={{ color: costColor(r.market_impact_cost_bps) }}
                >
                  {fmtBps(r.market_impact_cost_bps)}
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
