"use client";

import { useState } from "react";
import { BrinsonFachlerTable } from "./brinson-fachler-table";
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
  const [activeTab, setActiveTab] = useState<"brinson" | "risk">("brinson");

  return (
    <div className="space-y-4">
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

      <div className="flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--card)] p-1 w-fit">
        <button
          type="button"
          onClick={() => setActiveTab("brinson")}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "brinson"
              ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
        >
          Brinson-Fachler
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("risk")}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "risk"
              ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
        >
          Risk-Based
        </button>
      </div>

      {activeTab === "brinson" ? (
        <BrinsonFachlerTable portfolioId={portfolioId} start={start} end={end} />
      ) : (
        <RiskBasedChart portfolioId={portfolioId} start={start} end={end} />
      )}
    </div>
  );
}
