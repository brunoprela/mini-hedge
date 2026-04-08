"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { fxAttributionQueryOptions } from "../api";

interface Props {
  portfolioId: string;
  start: string;
  end: string;
}

function pct(v: string): string {
  return `${(parseFloat(v) * 100).toFixed(2)}%`;
}

function bps(v: string): string {
  return `${(parseFloat(v) * 10000).toFixed(1)}`;
}

function fxColor(v: string): string {
  const n = parseFloat(v);
  if (n > 0) return "text-[var(--success)]";
  if (n < 0) return "text-[var(--destructive)]";
  return "";
}

export function FXAttributionTable({ portfolioId, start, end }: Props) {
  const { fundSlug } = useFundContext();
  const { data, isLoading } = useQuery(
    fxAttributionQueryOptions(fundSlug, portfolioId, start, end),
  );

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading FX attribution...</div>;
  }

  if (!data?.entries) return null;

  return (
    <div className="space-y-2">
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="text-xs text-[var(--muted-foreground)]">Total FX Impact</p>
        <p className={`mt-0.5 font-mono text-sm font-semibold ${fxColor(data.total_fx_impact)}`}>
          {pct(data.total_fx_impact)}
        </p>
      </div>

      <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="px-3 py-1 font-medium">Currency</th>
              <th className="px-3 py-1 font-medium text-right">Weight (%)</th>
              <th className="px-3 py-1 font-medium text-right">Local Return (%)</th>
              <th className="px-3 py-1 font-medium text-right">FX Return (%)</th>
              <th className="px-3 py-1 font-medium text-right">Total Return (%)</th>
              <th className="px-3 py-1 font-medium text-right">Contribution (bps)</th>
            </tr>
          </thead>
          <tbody>
            {data.entries.map((entry) => (
              <tr key={entry.currency} className="border-b border-[var(--border)] last:border-0">
                <td className="px-3 py-2">
                  <Link
                    href={`/${fundSlug}/fx-hedging`}
                    className="text-[var(--primary)] hover:underline"
                  >
                    {entry.currency}
                  </Link>
                </td>
                <td className="px-3 py-2 text-right font-mono">{pct(entry.weight)}</td>
                <td className="px-3 py-2 text-right font-mono">{pct(entry.local_return)}</td>
                <td className={`px-3 py-2 text-right font-mono ${fxColor(entry.fx_return)}`}>
                  {pct(entry.fx_return)}
                </td>
                <td className="px-3 py-2 text-right font-mono">{pct(entry.total_return)}</td>
                <td className={`px-3 py-2 text-right font-mono ${fxColor(entry.contribution)}`}>
                  {bps(entry.contribution)}
                </td>
              </tr>
            ))}
            {data.entries.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-[var(--muted-foreground)]">
                  No FX data for this period.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
