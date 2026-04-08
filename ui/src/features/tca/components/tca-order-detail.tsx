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
          className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          {computeMutation.isPending ? "Computing..." : "Compute TCA"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Cost breakdown cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <CostCard label="Commission" bps={report.commission_bps} />
        <CostCard label="Spread" bps={report.spread_cost_bps} />
        <CostCard label="Timing" bps={report.timing_cost_bps} />
        <CostCard label="Impact" bps={report.impact_cost_bps} />
        <CostCard label="Opportunity" bps={report.opportunity_cost_bps} />
        <CostCard label="Total" bps={report.total_cost_bps} highlight />
      </div>

      {/* Cost decomposition bar */}
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Cost Decomposition
        </p>
        <CostBar
          items={[
            { label: "Commission", value: parseFloat(report.commission_bps), color: "#6366f1" },
            { label: "Spread", value: parseFloat(report.spread_cost_bps), color: "#f59e0b" },
            { label: "Timing", value: parseFloat(report.timing_cost_bps), color: "#ef4444" },
            { label: "Impact", value: parseFloat(report.impact_cost_bps), color: "#8b5cf6" },
            {
              label: "Opportunity",
              value: parseFloat(report.opportunity_cost_bps),
              color: "#6b7280",
            },
          ]}
        />
      </div>

      {/* Benchmark comparison */}
      <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">
          Benchmark Comparison
        </p>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">Arrival Price</p>
            <p className="font-mono text-sm font-semibold">{fmtPrice(report.arrival_price)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">Avg Fill Price</p>
            <p className="font-mono text-sm font-semibold">{fmtPrice(report.avg_fill_price)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--muted-foreground)]">VWAP</p>
            <p className="font-mono text-sm font-semibold">{fmtPrice(report.vwap)}</p>
          </div>
        </div>
      </div>

      {/* Execution metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
          <p className="text-xs text-[var(--muted-foreground)]">Participation Rate</p>
          <p className="mt-0.5 font-mono text-sm font-semibold">
            {fmtBps(report.participation_rate_pct)}%
          </p>
        </div>
        <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
          <p className="text-xs text-[var(--muted-foreground)]">Execution Duration</p>
          <p className="mt-0.5 font-mono text-sm font-semibold">
            {fmtDuration(report.execution_duration_seconds)}
          </p>
        </div>
        <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
          <p className="text-xs text-[var(--muted-foreground)]">Total Cost</p>
          <p className="mt-0.5 font-mono text-sm font-semibold">
            {fmtCurrency(report.total_cost_usd)}
          </p>
        </div>
        <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
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
        className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
      >
        {computeMutation.isPending ? "Recomputing..." : "Recompute TCA"}
      </button>
    </div>
  );
}

function CostCard({ label, bps, highlight }: { label: string; bps: string; highlight?: boolean }) {
  return (
    <div
      className="rounded-md border border-[var(--border)] bg-[var(--card)] p-3"
      style={highlight ? { borderColor: "var(--primary)" } : undefined}
    >
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold" style={{ color: costColor(bps) }}>
        {fmtBps(bps)}{" "}
        <span className="text-xs font-normal text-[var(--muted-foreground)]">bps</span>
      </p>
    </div>
  );
}

function CostBar({ items }: { items: { label: string; value: number; color: string }[] }) {
  const total = items.reduce((sum, i) => sum + Math.max(i.value, 0), 0);
  if (total <= 0) return null;

  return (
    <div>
      <div className="flex h-6 overflow-hidden rounded-full">
        {items.map((item) => {
          const pct = (Math.max(item.value, 0) / total) * 100;
          if (pct < 1) return null;
          return (
            <div
              key={item.label}
              className="flex items-center justify-center text-[8px] font-bold text-white"
              style={{ width: `${pct}%`, backgroundColor: item.color }}
              title={`${item.label}: ${item.value.toFixed(2)} bps`}
            >
              {pct > 12 ? `${item.value.toFixed(1)}` : ""}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-3">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5 text-xs">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[var(--muted-foreground)]">{item.label}</span>
            <span className="font-mono font-medium">{item.value.toFixed(2)} bps</span>
          </div>
        ))}
      </div>
    </div>
  );
}
