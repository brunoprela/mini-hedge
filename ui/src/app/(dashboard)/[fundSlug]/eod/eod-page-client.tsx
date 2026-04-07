"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar } from "lucide-react";
import { useState } from "react";
import { EODHistory, EODRunStatus, triggerEODRun } from "@/features/eod";
import { useFundContext } from "@/shared/hooks/use-fund-context";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function EODPageClient() {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState(todayISO());
  const [runDate, setRunDate] = useState(todayISO());

  const runMutation = useMutation({
    mutationFn: () => triggerEODRun(fundSlug, runDate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["eod-status"] });
      queryClient.invalidateQueries({ queryKey: ["eod-history"] });
      setSelectedDate(runDate);
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Calendar className="h-6 w-6 text-[var(--primary)]" />
        <h1 className="text-2xl font-semibold">EOD & NAV</h1>
      </div>

      {/* Trigger EOD */}
      <div className="flex items-end gap-3 rounded-lg border border-[var(--border)] p-4">
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
          onClick={() => runMutation.mutate()}
          disabled={runMutation.isPending}
          className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {runMutation.isPending ? "Running..." : "Run EOD"}
        </button>
        {runMutation.isError && (
          <p className="text-xs text-red-400">{(runMutation.error as Error).message}</p>
        )}
      </div>

      {/* Current run status */}
      <div>
        <div className="mb-3 flex items-center gap-3">
          <h2 className="text-lg font-medium">Run Status</h2>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-xs"
          />
        </div>
        <EODRunStatus businessDate={selectedDate} />
      </div>

      {/* History */}
      <div>
        <h2 className="mb-3 text-lg font-medium">Run History</h2>
        <EODHistory onSelectDate={setSelectedDate} />
      </div>
    </div>
  );
}
