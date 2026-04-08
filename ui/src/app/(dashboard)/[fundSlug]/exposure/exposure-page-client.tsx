"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ExposureBreakdowns } from "@/features/exposure/components/exposure-breakdowns";
import { ExposureHistoryChart } from "@/features/exposure/components/exposure-history-chart";
import { useExposureSummary } from "@/features/exposure/components/exposure-summary";
import { exposureQueryOptions } from "@/features/exposure/api";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { GaugeBar } from "@/shared/components/charts";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function ExposurePageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";
  const exposureSummary = useExposureSummary(activePortfolioId);

  const { data: exposure } = useQuery({
    ...exposureQueryOptions(fundSlug, activePortfolioId),
    enabled: !!activePortfolioId,
  });

  // Limit thresholds
  const grossLimit = 2_000_000;
  const netLimit = 1_000_000;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Exposure</h1>
        {portfolios && (
          <PortfolioSelector
            portfolios={portfolios}
            value={activePortfolioId}
            onChange={setSelectedPortfolioId}
          />
        )}
      </div>

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      {activePortfolioId && exposure && (
        <>
          {/* Summary strip */}
          {exposureSummary && (
            <div className="flex items-center gap-4 rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-2">
              {exposureSummary.map((item) => (
                <div key={item.label} className="flex items-baseline gap-1.5">
                  <span className="text-[10px] text-[var(--muted-foreground)]">{item.label}</span>
                  <span className="font-mono text-xs font-semibold">{item.value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Limit gauges */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
              <GaugeBar
                value={Math.abs(Number(exposure.gross_exposure))}
                max={grossLimit}
                label="Gross Exposure Utilization"
              />
              <p className="mt-1 text-center font-mono text-xs text-[var(--muted-foreground)]">
                {fmtCurrency(exposure.gross_exposure)} / {fmtCurrency(grossLimit)}
              </p>
            </div>
            <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
              <GaugeBar
                value={Math.abs(Number(exposure.net_exposure))}
                max={netLimit}
                label="Net Exposure Utilization"
              />
              <p className="mt-1 text-center font-mono text-xs text-[var(--muted-foreground)]">
                {fmtCurrency(exposure.net_exposure)} / {fmtCurrency(netLimit)}
              </p>
            </div>
          </div>

          {/* Breakdowns */}
          <SectionPanel title="Exposure Breakdowns">
            <div className="p-3">
              <ExposureBreakdowns portfolioId={activePortfolioId} />
            </div>
          </SectionPanel>

          {/* History */}
          <SectionPanel title="Exposure History">
            <div className="p-3">
              <ExposureHistoryChart portfolioId={activePortfolioId} />
            </div>
          </SectionPanel>
        </>
      )}
    </div>
  );
}
