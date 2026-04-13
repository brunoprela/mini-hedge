"use client";

import { useQuery } from "@tanstack/react-query";
import { exposureQueryOptions } from "@/features/exposure/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { fxHedgingSummaryQueryOptions } from "../api";

// ─── Helpers ───────────────────────────────────────────────

function gaugeColor(pct: number): string {
  if (pct >= 80) return "var(--success)";
  if (pct >= 50) return "var(--warning)";
  return "var(--destructive)";
}

function fmtPct(v: number): string {
  return `${v.toFixed(0)}%`;
}

function fmtNotional(v: number): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.abs(v));
}

// ─── Types ─────────────────────────────────────────────────

interface CurrencyHedgeRow {
  currency: string;
  exposure: number;
  hedged: number;
  ratio: number; // 0–100
}

// ─── Component ─────────────────────────────────────────────

export function HedgeCoverageGauges({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();

  const { data: summary } = useQuery(fxHedgingSummaryQueryOptions(fundSlug, portfolioId));
  const { data: exposure } = useQuery(exposureQueryOptions(fundSlug, portfolioId));

  if (!summary || !exposure) return null;

  // Build per-currency exposure from the exposure breakdowns
  const currencyExposures: Record<string, number> = {};
  for (const bd of exposure.breakdowns?.currency ?? []) {
    const net = Math.abs(Number(bd.net_value));
    if (net > 0) {
      currencyExposures[bd.key] = net;
    }
  }

  // currency_breakdown from FX summary = hedged notional per currency
  const hedgedByCcy = summary.currency_breakdown;

  // Merge: show every currency that appears in either set
  const allCurrencies = new Set([
    ...Object.keys(currencyExposures),
    ...Object.keys(hedgedByCcy),
  ]);

  const rows: CurrencyHedgeRow[] = [];
  for (const ccy of allCurrencies) {
    const exp = currencyExposures[ccy] ?? 0;
    const hedged = Math.abs(Number(hedgedByCcy[ccy] ?? 0));
    if (exp === 0 && hedged === 0) continue;
    const ratio = exp > 0 ? Math.min((hedged / exp) * 100, 100) : hedged > 0 ? 100 : 0;
    rows.push({ currency: ccy, exposure: exp, hedged, ratio });
  }

  // Sort by ratio ascending (least hedged first)
  rows.sort((a, b) => a.ratio - b.ratio);

  if (rows.length === 0) return null;

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="mb-3 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Hedge Coverage
      </p>
      <div className="space-y-2.5">
        {rows.map((row) => (
          <div key={row.currency}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-medium text-[var(--foreground)]">{row.currency}</span>
              <span className="tabular-nums text-[var(--muted-foreground)]">
                {fmtNotional(row.hedged)} / {fmtNotional(row.exposure)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${row.ratio}%`,
                    backgroundColor: gaugeColor(row.ratio),
                  }}
                />
              </div>
              <span
                className="w-10 text-right text-[10px] font-medium tabular-nums"
                style={{ color: gaugeColor(row.ratio) }}
              >
                {fmtPct(row.ratio)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
