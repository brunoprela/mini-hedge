"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { BrokerScorecardComparison } from "@/features/tca/components/broker-scorecard-comparison";
import { FundTCASummaryCard } from "@/features/tca/components/fund-tca-summary";
import { TCADashboard } from "@/features/tca/components/tca-dashboard";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type TCATab = "fund" | "portfolio" | "broker-scorecard";

const TABS: { id: TCATab; label: string }[] = [
  { id: "fund", label: "Fund Summary" },
  { id: "portfolio", label: "Portfolio Detail" },
  { id: "broker-scorecard", label: "Broker Scorecard" },
];

export function TCAPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<TCATab>("fund");
  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Transaction Cost Analysis</h1>
        {portfolios && (
          <PortfolioSelector
            portfolios={portfolios}
            value={activePortfolioId}
            onChange={setSelectedPortfolioId}
          />
        )}
      </div>

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      <SectionPanel
        title="Execution Quality"
        tabs={TABS.map((tab) => (
          <ToolbarTab
            key={tab.id}
            label={tab.label}
            active={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          />
        ))}
      >
        <div className="p-3">
          {activeTab === "fund" && <FundTCASummaryCard />}
          {activeTab === "portfolio" && activePortfolioId && (
            <TCADashboard portfolioId={activePortfolioId} />
          )}
          {activeTab === "broker-scorecard" && <BrokerScorecardComparison />}
        </div>
      </SectionPanel>
    </div>
  );
}
