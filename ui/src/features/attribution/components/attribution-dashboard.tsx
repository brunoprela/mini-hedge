"use client";

import { useCallback, useState } from "react";
import { BrinsonFachlerTable } from "./brinson-fachler-table";
import { FXAttributionTable } from "./fx-attribution-table";
import { RiskBasedChart } from "./risk-based-chart";

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

type PeriodPreset = "MTD" | "QTD" | "YTD" | "1Y" | "custom";

function computePresetStart(preset: Exclude<PeriodPreset, "custom">, today: Date): string {
  const y = today.getFullYear();
  const m = today.getMonth();
  switch (preset) {
    case "MTD":
      return formatDate(new Date(y, m, 1));
    case "QTD": {
      const qMonth = m - (m % 3);
      return formatDate(new Date(y, qMonth, 1));
    }
    case "YTD":
      return formatDate(new Date(y, 0, 1));
    case "1Y": {
      const oneYearAgo = new Date(today);
      oneYearAgo.setFullYear(y - 1);
      return formatDate(oneYearAgo);
    }
  }
}

const PERIOD_PRESETS: { id: Exclude<PeriodPreset, "custom">; label: string }[] = [
  { id: "MTD", label: "MTD" },
  { id: "QTD", label: "QTD" },
  { id: "YTD", label: "YTD" },
  { id: "1Y", label: "1Y" },
];

export function AttributionDashboard({ portfolioId }: { portfolioId: string }) {
  const today = new Date();

  const [activePeriod, setActivePeriod] = useState<PeriodPreset>("MTD");
  const [start, setStart] = useState(() => computePresetStart("MTD", today));
  const [end, setEnd] = useState(formatDate(today));
  const [activeTab, setActiveTab] = useState<"brinson" | "risk" | "fx">("brinson");

  const selectPreset = useCallback(
    (preset: Exclude<PeriodPreset, "custom">) => {
      setActivePeriod(preset);
      setStart(computePresetStart(preset, today));
      setEnd(formatDate(today));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const handleCustomDate = useCallback(
    (field: "start" | "end", value: string) => {
      setActivePeriod("custom");
      if (field === "start") setStart(value);
      else setEnd(value);
    },
    [],
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--card)] p-0.5">
          {PERIOD_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => selectPreset(p.id)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                activePeriod === p.id
                  ? "bg-[var(--primary)] text-white"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--border)]"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-[var(--border)]" />

        <label className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)]">
          Start
          <input
            type="date"
            value={start}
            onChange={(e) => handleCustomDate("start", e.target.value)}
            className="rounded-lg border border-[var(--input-border)] bg-[var(--input)] px-2 py-1 text-sm font-mono text-[var(--foreground)]"
          />
        </label>
        <label className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)]">
          End
          <input
            type="date"
            value={end}
            onChange={(e) => handleCustomDate("end", e.target.value)}
            className="rounded-lg border border-[var(--input-border)] bg-[var(--input)] px-2 py-1 text-sm font-mono text-[var(--foreground)]"
          />
        </label>
      </div>

      <div className="flex gap-1 border-b border-[var(--border)]">
        {[
          { id: "brinson" as const, label: "Brinson-Fachler" },
          { id: "risk" as const, label: "Risk-Based" },
          { id: "fx" as const, label: "FX" },
        ].map((tab) => (
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
      {activeTab === "risk" && <RiskBasedChart portfolioId={portfolioId} start={start} end={end} />}
      {activeTab === "fx" && (
        <FXAttributionTable portfolioId={portfolioId} start={start} end={end} />
      )}
    </div>
  );
}
