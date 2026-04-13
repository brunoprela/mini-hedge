"use client";

import { useQuery } from "@tanstack/react-query";
import { exposureQueryOptions } from "@/features/exposure/api";
import { GaugeBar } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { riskSnapshotQueryOptions } from "../api";

// ─── Default limits (could come from compliance config in the future) ───

const VAR_95_LIMIT = 200_000;
const VAR_99_LIMIT = 300_000;
const GROSS_EXPOSURE_LIMIT_PCT = 200; // percent of NAV
const NET_EXPOSURE_LIMIT_PCT = 100; // percent of NAV

// ─── Formatters ─────────────────────────────────────────────

const fmtCurrency = (v: number) =>
  v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

const fmtPct = (v: number) => `${v.toFixed(1)}%`;

// ─── Component ──────────────────────────────────────────────

interface RiskLimitGaugesProps {
  portfolioId: string;
}

export function RiskLimitGauges({ portfolioId }: RiskLimitGaugesProps) {
  const { fundSlug } = useFundContext();

  const { data: snapshot } = useQuery({
    ...riskSnapshotQueryOptions(fundSlug, portfolioId),
    enabled: !!portfolioId,
  });

  const { data: exposure } = useQuery({
    ...exposureQueryOptions(fundSlug, portfolioId),
    enabled: !!portfolioId,
  });

  if (!snapshot) return null;

  const nav = Number(snapshot.nav) || 1; // avoid division by zero

  const gauges: GaugeItem[] = [
    {
      label: "VaR 95% (1d)",
      value: Math.abs(Number(snapshot.var_95_1d)),
      max: VAR_95_LIMIT,
      formatValue: fmtCurrency,
      formatMax: fmtCurrency,
    },
    {
      label: "VaR 99% (1d)",
      value: Math.abs(Number(snapshot.var_99_1d)),
      max: VAR_99_LIMIT,
      formatValue: fmtCurrency,
      formatMax: fmtCurrency,
    },
    ...(exposure
      ? [
          {
            label: "Gross Exposure",
            value: (Math.abs(Number(exposure.gross_exposure)) / nav) * 100,
            max: GROSS_EXPOSURE_LIMIT_PCT,
            formatValue: fmtPct,
            formatMax: fmtPct,
          } satisfies GaugeItem,
          {
            label: "Net Exposure",
            value: (Math.abs(Number(exposure.net_exposure)) / nav) * 100,
            max: NET_EXPOSURE_LIMIT_PCT,
            formatValue: fmtPct,
            formatMax: fmtPct,
          } satisfies GaugeItem,
        ]
      : []),
  ];

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="mb-3 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Limit Utilization
      </p>
      <div className="space-y-3">
        {gauges.map((g) => (
          <GaugeBar
            key={g.label}
            value={g.value}
            max={g.max}
            label={g.label}
            formatValue={g.formatValue}
            formatMax={g.formatMax}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Types ──────────────────────────────────────────────────

interface GaugeItem {
  label: string;
  value: number;
  max: number;
  formatValue: (v: number) => string;
  formatMax: (v: number) => string;
}
