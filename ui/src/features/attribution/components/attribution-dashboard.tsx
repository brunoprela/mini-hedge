"use client";

import { useState } from "react";
import { BrinsonFachlerTable } from "./brinson-fachler-table";
import { FXAttributionTable } from "./fx-attribution-table";
import { RiskBasedChart } from "./risk-based-chart";

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function AttributionDashboard({ portfolioId }: { portfolioId: string }) {
  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const [start, setStart] = useState(formatDate(thirtyDaysAgo));
  const [end, setEnd] = useState(formatDate(today));
  const [activeTab, setActiveTab] = useState<"brinson" | "risk" | "fx">("brinson");

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)]">
          Start
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="rounded-lg border border-[var(--input-border)] bg-[var(--input)] px-2 py-1 text-sm font-mono text-[var(--foreground)]"
          />
        </label>
        <label className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)]">
          End
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="rounded-lg border border-[var(--input-border)] bg-[var(--input)] px-2 py-1 text-sm font-mono text-[var(--foreground)]"
          />
        </label>
      </div>

      <div className="flex gap-1 border-b border-[var(--border)]">
        {([
          { id: "brinson" as const, label: "Brinson-Fachler" },
          { id: "risk" as const, label: "Risk-Based" },
          { id: "fx" as const, label: "FX" },
        ]).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "brinson" && (
        <BrinsonFachlerTable portfolioId={portfolioId} start={start} end={end} />
      )}
      {activeTab === "risk" && (
        <RiskBasedChart portfolioId={portfolioId} start={start} end={end} />
      )}
      {activeTab === "fx" && (
        <FXAttributionTable portfolioId={portfolioId} start={start} end={end} />
      )}
    </div>
  );
}
