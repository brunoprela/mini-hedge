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

export function RiskDashboard({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: snapshot, isLoading } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

  const snapshotMutation = useMutation({
    mutationFn: () => takeRiskSnapshot(fundSlug, portfolioId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk-snapshot", fundSlug, portfolioId] });
    },
  });

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading risk snapshot...</div>;
  }

  if (!snapshot) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-[var(--muted-foreground)]">No risk snapshot available.</p>
        <button
          type="button"
          onClick={() => snapshotMutation.mutate()}
          disabled={snapshotMutation.isPending}
          className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          {snapshotMutation.isPending ? "Taking Snapshot..." : "Take Snapshot"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="VaR 95% (1d)" value={fmtCurrency(snapshot.var_95_1d)} />
        <StatCard label="VaR 99% (1d)" value={fmtCurrency(snapshot.var_99_1d)} />
        <StatCard
          label="Expected Shortfall 95%"
          value={fmtCurrency(snapshot.expected_shortfall_95)}
        />
        <StatCard label="NAV" value={fmtCurrency(snapshot.nav)} />
      </div>
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => snapshotMutation.mutate()}
          disabled={snapshotMutation.isPending}
          className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          {snapshotMutation.isPending ? "Taking Snapshot..." : "Take Snapshot"}
        </button>
        <span className="text-xs text-[var(--muted-foreground)]">
          Last: {new Date(snapshot.snapshot_at).toLocaleString()}
        </span>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}
