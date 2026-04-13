"use client";

import { useMemo } from "react";
import { WaterfallChart } from "@/shared/components/charts";
import type { BrinsonFachlerResult } from "../types";

interface Props {
  data: BrinsonFachlerResult;
}

export function ActiveReturnWaterfall({ data }: Props) {
  const items = useMemo(() => {
    const benchmarkReturn = parseFloat(data.benchmark_return);

    // Starting bar: benchmark return (rendered as a total so it starts from zero)
    const result: { label: string; value: number; isTotal?: boolean }[] = [
      { label: "Benchmark", value: benchmarkReturn, isTotal: true },
    ];

    // Intermediate bars: each sector's contribution to active return
    for (const sector of data.sectors) {
      const totalEffect = parseFloat(sector.total_effect);
      // Skip sectors with negligible contribution to keep the chart readable
      if (Math.abs(totalEffect) < 1e-6) continue;
      result.push({ label: sector.sector, value: totalEffect });
    }

    // Final bar: total portfolio return
    result.push({
      label: "Portfolio",
      value: parseFloat(data.portfolio_return),
      isTotal: true as const,
    });

    return result;
  }, [data]);

  if (items.length <= 2) return null;

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Active Return Waterfall
      </p>
      <WaterfallChart
        items={items}
        height={220}
        formatValue={(v) => `${(v * 100).toFixed(2)}%`}
      />
    </div>
  );
}
