"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ExposureBreakdowns } from "@/features/exposure/components/exposure-breakdowns";
import { ExposureHistoryChart } from "@/features/exposure/components/exposure-history-chart";
import { useExposureSummary } from "@/features/exposure/components/exposure-summary";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type ExposureTab = "summary" | "history";

const TABS: { id: ExposureTab; label: string }[] = [
  { id: "summary", label: "Breakdowns" },
  { id: "history", label: "History" },
];

export function ExposurePageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<ExposureTab>("summary");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";
  const exposureSummary = useExposureSummary(activePortfolioId);

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

      {activePortfolioId && exposureSummary && (
        <SectionPanel
          title="Exposure Analysis"
          tabs={
            <>
              {TABS.map((tab) => (
                <ToolbarTab
                  key={tab.id}
                  label={tab.label}
                  active={activeTab === tab.id}
                  onClick={() => setActiveTab(tab.id)}
                />
              ))}
            </>
          }
          summary={exposureSummary}
        >
          <div className="p-3">
            {activeTab === "summary" && (
              <ExposureBreakdowns portfolioId={activePortfolioId} />
            )}
            {activeTab === "history" && (
              <ExposureHistoryChart portfolioId={activePortfolioId} />
            )}
          </div>
        </SectionPanel>
      )}
    </div>
  );
}
