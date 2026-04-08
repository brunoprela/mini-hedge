"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { riskSnapshotQueryOptions, takeRiskSnapshot } from "../api";

function fmtCurrency(v: string) {
  const n = parseFloat(v);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

/** Returns summary items for use in SectionPanel summary prop. */
export function useRiskSummary(portfolioId: string) {
  const { fundSlug } = useFundContext();
  const { data: snapshot, isLoading } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

  if (isLoading || !snapshot) return null;

  return [
    { label: "VaR 95% (1d)", value: fmtCurrency(snapshot.var_95_1d) },
    { label: "VaR 99% (1d)", value: fmtCurrency(snapshot.var_99_1d) },
    { label: "ES 95%", value: fmtCurrency(snapshot.expected_shortfall_95) },
    { label: "NAV", value: fmtCurrency(snapshot.nav) },
  ];
}

/** Exported so the page can place it in the header. */
export function SnapshotButton({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: snapshot } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

  const snapshotMutation = useMutation({
    mutationFn: () => takeRiskSnapshot(fundSlug, portfolioId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk-snapshot", fundSlug, portfolioId] });
      queryClient.invalidateQueries({ queryKey: ["risk-history"] });
    },
  });

  if (!snapshot) return null;

  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-[var(--muted-foreground)]">
        {new Date(snapshot.snapshot_at).toLocaleString()}
      </span>
      <button
        type="button"
        onClick={() => snapshotMutation.mutate()}
        disabled={snapshotMutation.isPending}
        className="rounded-md bg-[var(--primary)] px-2.5 py-1 text-[10px] font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
      >
        {snapshotMutation.isPending ? "Snapshotting..." : "Snapshot"}
      </button>
    </div>
  );
}

/** Initial snapshot prompt — shown when no snapshot exists. */
export function RiskSnapshotPrompt({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: snapshot, isLoading } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

  const snapshotMutation = useMutation({
    mutationFn: () => takeRiskSnapshot(fundSlug, portfolioId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk-snapshot", fundSlug, portfolioId] });
    },
  });

  if (isLoading) return <div className="text-xs text-[var(--muted-foreground)]">Loading...</div>;
  if (snapshot) return null;

  return (
    <div className="flex items-center gap-3 rounded-md border border-dashed border-[var(--border)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">No risk snapshot yet.</p>
      <button
        type="button"
        onClick={() => snapshotMutation.mutate()}
        disabled={snapshotMutation.isPending}
        className="rounded-md bg-[var(--primary)] px-3 py-1 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
      >
        {snapshotMutation.isPending ? "Taking Snapshot..." : "Take Snapshot"}
      </button>
    </div>
  );
}
