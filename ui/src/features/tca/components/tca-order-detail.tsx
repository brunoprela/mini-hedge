"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { computeTCA, orderTCAQueryOptions } from "../api";

function fmtBps(v: string) {
  return parseFloat(v).toFixed(2);
}

function fmtCurrency(v: string) {
  return parseFloat(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function fmtPrice(v: string) {
  return parseFloat(v).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

function fmtDuration(seconds: string) {
  const s = parseFloat(seconds);
  if (s < 60) return `${s.toFixed(1)}s`;
  if (s < 3600) return `${(s / 60).toFixed(1)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}

function costColor(bps: string) {
  const n = parseFloat(bps);
  if (n <= 2) return "var(--success)";
  if (n <= 5) return "var(--foreground)";
  return "var(--destructive)";
}

export function TCAOrderDetail({ orderId }: { orderId: string }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const { data: report, isLoading } = useQuery(orderTCAQueryOptions(fundSlug, orderId));

  const computeMutation = useMutation({
    mutationFn: () => computeTCA(fundSlug, orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order-tca", fundSlug, orderId] });
      toast.success("TCA computed successfully");
    },
    onError: () => {
      toast.error("Failed to compute TCA");
    },
  });

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading TCA report...</div>;
  }

  if (!report) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-[var(--muted-foreground)]">
          No TCA data available for this order.
        </p>
        <button
          type="button"
          onClick={() => computeMutation.mutate()}
          disabled={computeMutation.isPending}
          className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          {computeMutation.isPending ? "Computing..." : "Compute TCA"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Cost breakdown cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <CostCard label="Commission" bps={report.commission_bps} />
        <CostCard label="Spread" bps={report.spread_cost_bps} />
        <CostCard label="Timing" bps={report.timing_cost_bps} />
        <CostCard label="Impact" bps={report.impact_cost_bps} />
        <CostCard label="Opportunity" bps={report.opportunity_cost_bps} />
        <CostCard label="Total" bps={report.total_cost_bps} highlight />
      </div>

      {/* Benchmark comparison */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">
          Benchmark Comparison
        </p>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">Arrival Price</p>
            <p className="font-mono text-base font-semibold">{fmtPrice(report.arrival_price)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">Avg Fill Price</p>
            <p className="font-mono text-base font-semibold">{fmtPrice(report.avg_fill_price)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">VWAP</p>
            <p className="font-mono text-base font-semibold">{fmtPrice(report.vwap)}</p>
          </div>
        </div>
      </div>

      {/* Execution metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
          <p className="text-xs text-[var(--muted-foreground)]">Participation Rate</p>
          <p className="mt-1 font-mono text-lg font-semibold">
            {fmtBps(report.participation_rate_pct)}%
          </p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
          <p className="text-xs text-[var(--muted-foreground)]">Execution Duration</p>
          <p className="mt-1 font-mono text-lg font-semibold">
            {fmtDuration(report.execution_duration_seconds)}
          </p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
          <p className="text-xs text-[var(--muted-foreground)]">Total Cost</p>
          <p className="mt-1 font-mono text-lg font-semibold">
            {fmtCurrency(report.total_cost_usd)}
          </p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
          <p className="text-xs text-[var(--muted-foreground)]">Computed At</p>
          <p className="mt-1 text-sm font-medium">
            {new Date(report.computed_at).toLocaleString()}
          </p>
        </div>
      </div>

      {/* Recompute button */}
      <button
        type="button"
        onClick={() => computeMutation.mutate()}
        disabled={computeMutation.isPending}
        className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
      >
        {computeMutation.isPending ? "Recomputing..." : "Recompute TCA"}
      </button>
    </div>
  );
}

function CostCard({
  label,
  bps,
  highlight,
}: {
  label: string;
  bps: string;
  highlight?: boolean;
}) {
  return (
    <div
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3"
      style={highlight ? { borderColor: "var(--primary)" } : undefined}
    >
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p
        className="mt-1 font-mono text-lg font-semibold"
        style={{ color: costColor(bps) }}
      >
        {fmtBps(bps)} <span className="text-xs font-normal text-[var(--muted-foreground)]">bps</span>
      </p>
    </div>
  );
}
