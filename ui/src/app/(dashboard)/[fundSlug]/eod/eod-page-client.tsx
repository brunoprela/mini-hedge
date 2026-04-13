"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { EODHistory, EODRunStatus, NAVHistoryChart, triggerEODRun } from "@/features/eod";
import { StatusDot } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

const EOD_STEPS = ["Price Sync", "P&L Calc", "NAV", "Compliance", "Complete"];

export function EODPageClient() {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState(todayISO());
  const [runDate, setRunDate] = useState(todayISO());

  const runMutation = useMutation({
    mutationFn: (date?: string) => triggerEODRun(fundSlug, date ?? runDate),
    onSuccess: (_data, date) => {
      queryClient.invalidateQueries({ queryKey: ["eod-status"] });
      queryClient.invalidateQueries({ queryKey: ["eod-history"] });
      setSelectedDate(date ?? runDate);
    },
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">EOD &amp; NAV</h1>
      </div>

      {/* Trigger EOD + Progress Steps */}
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <div className="flex items-end gap-3">
          <div>
            <label
              htmlFor="eod-date"
              className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]"
            >
              Business Date
            </label>
            <input
              id="eod-date"
              type="date"
              value={runDate}
              onChange={(e) => setRunDate(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="button"
            onClick={() => runMutation.mutate(undefined)}
            disabled={runMutation.isPending}
            className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {runMutation.isPending ? "Running..." : "Run EOD"}
          </button>
          {runMutation.isError && (
            <p className="text-xs text-red-400">{(runMutation.error as Error).message}</p>
          )}
        </div>

        {/* Step progress bar */}
        {runMutation.isPending && (
          <div className="mt-4 flex items-center gap-1">
            {EOD_STEPS.map((step, i) => (
              <div key={step} className="flex flex-1 items-center gap-1.5">
                <StatusDot variant={i === 0 ? "info" : "neutral"} size={7} />
                <span className="text-[10px] font-medium text-[var(--muted-foreground)]">
                  {step}
                </span>
                {i < EOD_STEPS.length - 1 && <div className="h-px flex-1 bg-[var(--border)]" />}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* NAV History Chart */}
      <NAVHistoryChart />

      {/* Current run status */}
      <div>
        <div className="mb-2 flex items-center gap-3">
          <h2 className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Run Status
          </h2>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-xs"
          />
        </div>
        <EODRunStatus
          businessDate={selectedDate}
          onRerun={(date) => runMutation.mutate(date)}
          isRerunPending={runMutation.isPending}
        />
      </div>

      {/* History */}
      <div>
        <h2 className="mb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Run History
        </h2>
        <EODHistory onSelectDate={setSelectedDate} />
      </div>
    </div>
  );
}
