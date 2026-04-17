"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CardSkeleton } from "@mini-hedge/ui";
import { CashDashboard } from "@/features/cash/components/cash-dashboard";
import { CashProjection } from "@/features/cash/components/cash-projection";
import { SettlementLadder } from "@/features/cash/components/settlement-ladder";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type CashTab = "balances" | "settlements" | "projection";

const TABS: { id: CashTab; label: string }[] = [
  { id: "balances", label: "Balances" },
  { id: "settlements", label: "Settlement Ladder" },
  { id: "projection", label: "Cash Projection" },
];

export function CashPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<CashTab>("balances");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Cash Management</h1>
        {portfolios && (
          <PortfolioSelector
            portfolios={portfolios}
            value={activePortfolioId}
            onChange={setSelectedPortfolioId}
          />
        )}
      </div>

      {isLoading && <CardSkeleton count={3} />}

      {activePortfolioId && (
        <SectionPanel
          title="Cash & Settlements"
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
            {activeTab === "balances" && <CashDashboard portfolioId={activePortfolioId} />}
            {activeTab === "settlements" && <SettlementLadder portfolioId={activePortfolioId} />}
            {activeTab === "projection" && <CashProjection portfolioId={activePortfolioId} />}
          </div>
        </SectionPanel>
      )}
    </div>
  );
}
