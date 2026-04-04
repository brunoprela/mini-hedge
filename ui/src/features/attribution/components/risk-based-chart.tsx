"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { riskBasedQueryOptions } from "../api";

interface Props {
  portfolioId: string;
  start: string;
  end: string;
}

function pct(v: string): string {
  return `${(parseFloat(v) * 100).toFixed(2)}%`;
}

function currency(v: string): string {
  return parseFloat(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function RiskBasedChart({ portfolioId, start, end }: Props) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(riskBasedQueryOptions(fundSlug, portfolioId, start, end));

  if (isLoading) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">Loading risk attribution...</div>
    );
  }

  if (!data) {
    return (
      <div className="text-sm text-[var(--muted-foreground)]">
        No risk attribution data available.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard label="Total PnL" value={currency(data.total_pnl)} />
        <SummaryCard label="Systematic PnL" value={currency(data.systematic_pnl)} />
        <SummaryCard label="Idiosyncratic PnL" value={currency(data.idiosyncratic_pnl)} />
        <SummaryCard label="Systematic %" value={pct(data.systematic_pct)} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="px-3 py-2 font-medium">Factor</th>
              <th className="px-3 py-2 font-medium text-right">Factor Return</th>
              <th className="px-3 py-2 font-medium text-right">Portfolio Exposure</th>
              <th className="px-3 py-2 font-medium text-right">PnL Contribution</th>
              <th className="px-3 py-2 font-medium text-right">% of Total</th>
            </tr>
          </thead>
          <tbody>
            {data.factor_contributions.map((f) => (
              <tr key={f.factor} className="border-b border-[var(--border)] last:border-0">
                <td className="px-3 py-2">{f.factor}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(f.factor_return)}</td>
                <td className="px-3 py-2 text-right font-mono">
                  {parseFloat(f.portfolio_exposure).toFixed(3)}
                </td>
                <td className="px-3 py-2 text-right font-mono">{currency(f.pnl_contribution)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(f.pct_of_total)}</td>
              </tr>
            ))}
            {data.factor_contributions.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-center text-[var(--muted-foreground)]">
                  No factor data for this period.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}
