"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { riskSnapshotQueryOptions } from "@/features/risk/api";
import { CustomStressForm } from "@/features/risk/components/custom-stress-form";
import { FactorBreakdown } from "@/features/risk/components/factor-breakdown";
import { PnLContributors } from "@/features/risk/components/pnl-contributors";
import {
  RiskSnapshotPrompt,
  SnapshotButton,
  useRiskSummary,
} from "@/features/risk/components/risk-dashboard";
import { RiskHistoryChart, useHasRiskHistory } from "@/features/risk/components/risk-history-chart";
import { StressTable } from "@/features/risk/components/stress-table";
import { VaRContributions } from "@/features/risk/components/var-contributions";
import { GaugeBar } from "@/shared/components/charts";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

type RiskTab = "overview" | "pnl" | "stress";

const TABS: { id: RiskTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "pnl", label: "P&L & VaR" },
  { id: "stress", label: "Stress Tests" },
];

export function RiskPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<RiskTab>("overview");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";
  const hasHistory = useHasRiskHistory(activePortfolioId);
  const riskSummary = useRiskSummary(activePortfolioId);

  const { data: snapshot } = useQuery({
    ...riskSnapshotQueryOptions(fundSlug, activePortfolioId),
    enabled: !!activePortfolioId,
  });

  // Limit thresholds (could come from compliance config in the future)
  const varLimit = 200_000;
  const esLimit = 300_000;
  const drawdownLimit = 5; // percent

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Risk</h1>
        <div className="flex items-center gap-3">
          {activePortfolioId && <SnapshotButton portfolioId={activePortfolioId} />}
          {portfolios && (
            <PortfolioSelector
              portfolios={portfolios}
              value={activePortfolioId}
              onChange={setSelectedPortfolioId}
            />
          )}
        </div>
      </div>

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      {activePortfolioId && (
        <>
          <RiskSnapshotPrompt portfolioId={activePortfolioId} />

          {/* KPI Limit Gauges */}
          {snapshot && (
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
                <GaugeBar
                  value={Math.abs(Number(snapshot.var_95_1d))}
                  max={varLimit}
                  label="VaR 95% (1d) Utilization"
                />
                <p className="mt-1 text-center font-mono text-xs text-[var(--muted-foreground)]">
                  {fmtCurrency(snapshot.var_95_1d)} / {fmtCurrency(String(varLimit))}
                </p>
              </div>
              <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
                <GaugeBar
                  value={Math.abs(Number(snapshot.expected_shortfall_95))}
                  max={esLimit}
                  label="Expected Shortfall 95% Utilization"
                />
                <p className="mt-1 text-center font-mono text-xs text-[var(--muted-foreground)]">
                  {fmtCurrency(snapshot.expected_shortfall_95)} / {fmtCurrency(String(esLimit))}
                </p>
              </div>
              <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
                <GaugeBar
                  value={Math.abs(Number(snapshot.max_drawdown) * 100)}
                  max={drawdownLimit}
                  label="Max Drawdown Utilization"
                />
                <p className="mt-1 text-center font-mono text-xs text-[var(--muted-foreground)]">
                  {(Number(snapshot.max_drawdown) * 100).toFixed(2)}% / {drawdownLimit}%
                </p>
              </div>
            </div>
          )}

          {riskSummary && (
            <SectionPanel
              title="Risk Overview"
              tabs={TABS.map((tab) => (
                <ToolbarTab
                  key={tab.id}
                  label={tab.label}
                  active={activeTab === tab.id}
                  onClick={() => setActiveTab(tab.id)}
                />
              ))}
              summary={riskSummary}
            >
              <div className="p-3">
                {activeTab === "overview" && (
                  <div className="space-y-3">
                    {hasHistory && <RiskHistoryChart portfolioId={activePortfolioId} />}
                    <FactorBreakdown portfolioId={activePortfolioId} fullWidth={true} />
                  </div>
                )}

                {activeTab === "pnl" && (
                  <div className="grid grid-cols-2 gap-3">
                    <PnLContributors portfolioId={activePortfolioId} />
                    <VaRContributions portfolioId={activePortfolioId} />
                  </div>
                )}

                {activeTab === "stress" && (
                  <div className="grid grid-cols-12 gap-3">
                    <div className="col-span-8">
                      <StressTable portfolioId={activePortfolioId} />
                    </div>
                    <div className="col-span-4">
                      <CustomStressForm portfolioId={activePortfolioId} />
                    </div>
                  </div>
                )}
              </div>
            </SectionPanel>
          )}
        </>
      )}
    </div>
  );
}
