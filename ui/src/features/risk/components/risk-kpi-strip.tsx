"use client";

import { useQuery } from "@tanstack/react-query";
import { exposureQueryOptions } from "@/features/exposure/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { riskSnapshotQueryOptions } from "../api";

// ─── Formatters ────────────────────────────────────────────

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

const fmtPct = (v: number) => `${v.toFixed(2)}%`;

const fmtRatio = (v: number) => v.toFixed(2);

// ─── Component ─────────────────────────────────────────────

interface RiskKpiStripProps {
  portfolioId: string;
}

export function RiskKpiStrip({ portfolioId }: RiskKpiStripProps) {
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

  // Thresholds for color indicators
  const varLimit = 200_000;
  const varUtilization = Math.abs(Number(snapshot.var_95_1d)) / varLimit;
  const drawdownPct = Math.abs(Number(snapshot.max_drawdown) * 100);
  const sharpe = snapshot.sharpe_ratio != null ? Number(snapshot.sharpe_ratio) : null;

  const kpis: KpiItem[] = [
    {
      label: "VaR 95% (1d)",
      value: fmtCurrency(snapshot.var_95_1d),
      color:
        varUtilization >= 0.9
          ? "var(--destructive)"
          : varUtilization >= 0.7
            ? "var(--warning)"
            : "var(--foreground)",
      sublabel: `${(varUtilization * 100).toFixed(0)}% of limit`,
    },
    {
      label: "VaR 99% (1d)",
      value: fmtCurrency(snapshot.var_99_1d),
      color: "var(--foreground)",
    },
    {
      label: "Expected Shortfall",
      value: fmtCurrency(snapshot.expected_shortfall_95),
      color: "var(--foreground)",
      sublabel: "95% confidence",
    },
    {
      label: "Max Drawdown",
      value: fmtPct(drawdownPct),
      color:
        drawdownPct >= 4
          ? "var(--destructive)"
          : drawdownPct >= 2.5
            ? "var(--warning)"
            : "var(--success)",
    },
    ...(sharpe != null
      ? [
          {
            label: "Sharpe Ratio",
            value: fmtRatio(sharpe),
            color:
              sharpe >= 1
                ? "var(--success)"
                : sharpe >= 0.5
                  ? "var(--foreground)"
                  : "var(--destructive)",
          } satisfies KpiItem,
        ]
      : []),
    ...(exposure
      ? [
          {
            label: "Gross Exposure",
            value: fmtCurrency(exposure.gross_exposure),
            color: "var(--foreground)",
            sublabel: `${exposure.long_count}L / ${exposure.short_count}S`,
          } satisfies KpiItem,
          {
            label: "Net Exposure",
            value: fmtCurrency(exposure.net_exposure),
            color:
              Number(exposure.net_exposure) >= 0 ? "var(--success)" : "var(--destructive)",
          } satisfies KpiItem,
        ]
      : []),
  ];

  return (
    <dl
      className="grid gap-px overflow-hidden rounded-lg bg-[var(--border)]"
      style={{ gridTemplateColumns: `repeat(${kpis.length}, minmax(0, 1fr))` }}
    >
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className="bg-[var(--card)] px-4 py-3"
        >
          <dt className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
            {kpi.label}
          </dt>
          <dd className="mt-1 font-mono text-lg font-bold" style={{ color: kpi.color }}>
            {kpi.value}
          </dd>
          {kpi.sublabel && (
            <dd className="mt-0.5 text-[10px] text-[var(--muted-foreground)]">{kpi.sublabel}</dd>
          )}
        </div>
      ))}
    </dl>
  );
}

// ─── Types ─────────────────────────────────────────────────

interface KpiItem {
  label: string;
  value: string;
  color: string;
  sublabel?: string;
}
