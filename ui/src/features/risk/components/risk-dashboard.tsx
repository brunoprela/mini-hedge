"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { InfoTooltip } from "@/shared/components/table-controls";
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
        <StatCard
          label="VaR 95% (1d)"
          value={fmtCurrency(snapshot.var_95_1d)}
          info="Maximum expected daily loss at 95% confidence"
        />
        <StatCard
          label="VaR 99% (1d)"
          value={fmtCurrency(snapshot.var_99_1d)}
          info="Maximum expected daily loss at 99% confidence"
        />
        <StatCard
          label="Expected Shortfall 95%"
          value={fmtCurrency(snapshot.expected_shortfall_95)}
          info="Average loss in the worst 5% of scenarios (CVaR)"
        />
        <StatCard
          label="NAV"
          value={fmtCurrency(snapshot.nav)}
          info="Net Asset Value — total portfolio market value"
        />
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

function StatCard({ label, value, info }: { label: string; value: string; info?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <p className="inline-flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
        {label}
        {info && <InfoTooltip text={info} />}
      </p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}
