"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api";
import { StatusBadge } from "@/shared/components/status-badge";
import type {
  FundDetail,
  UserInfo,
  AuditEntry,
  SubscriptionRequestSummary,
  RedemptionRequestSummary,
  Page,
} from "@/shared/types";

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function DashboardPage() {
  const funds = useQuery({
    queryKey: ["admin", "funds", { limit: 1 }],
    queryFn: () => apiFetch<Page<FundDetail>>("admin/funds?limit=1"),
  });

  const users = useQuery({
    queryKey: ["admin", "users", { limit: 1 }],
    queryFn: () => apiFetch<Page<UserInfo>>("admin/users?limit=1"),
  });

  const audit = useQuery({
    queryKey: ["admin", "audit", { limit: 5 }],
    queryFn: () => apiFetch<Page<AuditEntry>>("admin/audit?limit=5"),
  });

  const pendingSubs = useQuery({
    queryKey: ["investor-ops", "subscriptions", "pending"],
    queryFn: () =>
      apiFetch<SubscriptionRequestSummary[]>(
        "investor-operations/subscriptions?state=pending_ops_review",
      ),
  });

  const pendingReds = useQuery({
    queryKey: ["investor-ops", "redemptions", "pending"],
    queryFn: () =>
      apiFetch<RedemptionRequestSummary[]>(
        "investor-operations/redemptions?state=pending_validation",
      ),
  });

  const isLoading =
    funds.isLoading ||
    users.isLoading ||
    audit.isLoading ||
    pendingSubs.isLoading ||
    pendingReds.isLoading;

  const subsData = pendingSubs.data ?? [];
  const redsData = pendingReds.data ?? [];

  const workflowItems = [
    ...subsData.map((s) => ({
      type: "Sub" as const,
      investorId: s.investor_id,
      amount: s.requested_amount,
      state: s.state,
      submittedAt: s.submitted_at,
    })),
    ...redsData.map((r) => ({
      type: "Red" as const,
      investorId: r.investor_id,
      amount: r.requested_amount,
      state: r.state,
      submittedAt: r.submitted_at,
    })),
  ];

  const auditItems = audit.data?.items ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-[var(--foreground)]">Operations Dashboard</h1>

      {/* KPI strip */}
      <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-4">
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Total Funds
          </dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
            {isLoading ? "..." : (funds.data?.total ?? 0)}
          </dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Total Users
          </dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
            {isLoading ? "..." : (users.data?.total ?? 0)}
          </dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Pending Subscriptions
          </dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
            {isLoading ? "..." : subsData.length}
          </dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Pending Redemptions
          </dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
            {isLoading ? "..." : redsData.length}
          </dd>
        </div>
      </dl>

      {/* Two-column grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Workflow Queue */}
        <div className="rounded-lg border border-[var(--border)] bg-white">
          <div className="border-b border-[var(--border)] px-4 py-3">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Workflow Queue</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Type</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Investor</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Amount</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">State</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Submitted At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {isLoading && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">Loading...</td>
                  </tr>
                )}
                {!isLoading && workflowItems.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">
                      No pending items
                    </td>
                  </tr>
                )}
                {workflowItems.map((item, i) => (
                  <tr key={`${item.type}-${i}`} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={item.type}
                        variant={item.type === "Sub" ? "success" : "warning"}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm font-mono" title={item.investorId}>
                      {item.investorId.slice(0, 8)}
                    </td>
                    <td className="px-3 py-2 text-sm font-mono">
                      {item.amount.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge label={item.state} variant="neutral" />
                    </td>
                    <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">
                      {new Date(item.submittedAt).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="rounded-lg border border-[var(--border)] bg-white">
          <div className="border-b border-[var(--border)] px-4 py-3">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Recent Activity</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Event Type</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fund</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {isLoading && (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">Loading...</td>
                  </tr>
                )}
                {!isLoading && auditItems.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">
                      No recent activity
                    </td>
                  </tr>
                )}
                {auditItems.map((entry) => (
                  <tr key={entry.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm text-[var(--foreground)]">{entry.event_type}</td>
                    <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]">{entry.fund_slug ?? "\u2014"}</td>
                    <td className="px-3 py-2 text-sm text-[var(--muted-foreground)]">
                      {formatRelativeTime(entry.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
