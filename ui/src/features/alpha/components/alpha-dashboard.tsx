"use client";

import { useState } from "react";
import { OptimizationPanel } from "./optimization-panel";
import { OrderIntentsTable } from "./order-intents-table";
import { WhatIfForm } from "./what-if-form";

const TABS = ["What-If", "Optimization", "Order Intents"] as const;
type Tab = (typeof TABS)[number];

export function AlphaDashboard({ portfolioId }: { portfolioId: string }) {
  const [activeTab, setActiveTab] = useState<Tab>("What-If");

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab
                ? "border-b-2 border-[var(--foreground)] text-[var(--foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "What-If" && <WhatIfForm portfolioId={portfolioId} />}
      {activeTab === "Optimization" && <OptimizationPanel portfolioId={portfolioId} />}
      {activeTab === "Order Intents" && <OrderIntentsTable portfolioId={portfolioId} />}
    </div>
  );
}
