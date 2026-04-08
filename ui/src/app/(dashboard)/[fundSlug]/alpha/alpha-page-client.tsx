"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { OptimizationPanel } from "@/features/alpha/components/optimization-panel";
import { OrderIntentsTable } from "@/features/alpha/components/order-intents-table";
import { WhatIfForm } from "@/features/alpha/components/what-if-form";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type AlphaTab = "what-if" | "optimization" | "intents";

const TABS: { id: AlphaTab; label: string }[] = [
  { id: "what-if", label: "What-If Scenario" },
  { id: "optimization", label: "Optimization" },
  { id: "intents", label: "Order Intents" },
];

export function AlphaPageClient() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<AlphaTab>("what-if");

  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Alpha Engine</h1>
        {portfolios && (
          <PortfolioSelector
            portfolios={portfolios}
            value={activePortfolioId}
            onChange={setSelectedPortfolioId}
          />
        )}
      </div>

      {isLoading && <p className="text-xs text-[var(--muted-foreground)]">Loading...</p>}

      {activePortfolioId && (
        <SectionPanel
          title="Alpha Tools"
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
            {activeTab === "what-if" && <WhatIfForm portfolioId={activePortfolioId} />}
            {activeTab === "optimization" && <OptimizationPanel portfolioId={activePortfolioId} />}
            {activeTab === "intents" && <OrderIntentsTable portfolioId={activePortfolioId} />}
          </div>
        </SectionPanel>
      )}
    </div>
  );
}
