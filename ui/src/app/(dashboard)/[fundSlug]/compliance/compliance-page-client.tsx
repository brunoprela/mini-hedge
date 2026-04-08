"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { violationsQueryOptions, waiveViolation } from "@/features/compliance/api";
import { RemediationPanel } from "@/features/compliance/components/remediation-panel";
import { RuleTable } from "@/features/compliance/components/rule-table";
import type { Violation } from "@/features/compliance/types";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { DonutChart, StatusDot } from "@/shared/components/charts";
import { PortfolioSelector } from "@/shared/components/portfolio-selector";
import { SectionPanel, ToolbarTab } from "@/shared/components/section-panel";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { clientFetch } from "@/shared/lib/api";
import { cn } from "@/shared/lib/cn";
import { Permission } from "@/shared/lib/permissions";

type TabId = "dashboard" | "violations" | "rules";

const SEVERITY_BADGE: Record<string, string> = {
  block: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
  warning: "bg-[var(--warning-muted)] text-[var(--warning)]",
  breach: "bg-[var(--accent-orange-muted)] text-[var(--accent-orange)]",
};

function severityDotVariant(severity: string): "error" | "warning" | "info" {
  switch (severity) {
    case "block":
      return "error";
    case "warning":
      return "warning";
    default:
      return "info";
  }
}

export function CompliancePageClient() {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const queryClient = useQueryClient();
  const exportCSV = useExportCSV();

  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const [selectedViolationId, setSelectedViolationId] = useState<string | null>(null);
  const [waiveReason, setWaiveReason] = useState("");
  const [severityFilter, setSeverityFilter] = useState<"all" | "block" | "warning" | "breach">(
    "all",
  );

  const canWrite = can(Permission.COMPLIANCE_WRITE);
  const activePortfolioId = selectedPortfolioId || portfolios?.[0]?.id || "";

  const { data: violations, isLoading } = useQuery({
    ...violationsQueryOptions(fundSlug, activePortfolioId),
    enabled: !!activePortfolioId,
  });

  const filteredViolations = useMemo(() => {
    if (!violations) return [];
    if (severityFilter === "all") return violations;
    return violations.filter((v) => v.severity === severityFilter);
  }, [violations, severityFilter]);

  const blockCount = violations?.filter((v) => v.severity === "block").length ?? 0;
  const warningCount = violations?.filter((v) => v.severity === "warning").length ?? 0;
  const breachCount = violations?.filter((v) => v.severity === "breach").length ?? 0;

  // Mutations
  const resolveMutation = useMutation({
    mutationFn: (violationId: string) =>
      clientFetch<Violation>(`/compliance/violations/${violationId}/resolve`, {
        fundSlug,
        method: "POST",
        body: { resolved_by: "current_user" },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
      toast.success("Violation resolved");
      setSelectedViolationId(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const waiveMutation = useMutation({
    mutationFn: ({ violationId, reason }: { violationId: string; reason: string }) =>
      waiveViolation(fundSlug, violationId, { waived_by: "current_user", reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
      toast.success("Violation waived");
      setSelectedViolationId(null);
      setWaiveReason("");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleExport = () => {
    if (!filteredViolations.length) return;
    exportCSV(
      filteredViolations.map((v) => ({
        rule: v.rule_name,
        severity: v.severity,
        message: v.message,
        current_value: v.current_value ?? "",
        limit_value: v.limit_value ?? "",
        detected_at: v.detected_at,
      })) as unknown as Record<string, unknown>[],
      `violations-${activePortfolioId}`,
    );
  };

  // Tabs shared across all views
  const tabs = (
    <>
      <ToolbarTab
        label="Dashboard"
        active={activeTab === "dashboard"}
        onClick={() => setActiveTab("dashboard")}
      />
      <ToolbarTab
        label="Violations"
        active={activeTab === "violations"}
        onClick={() => setActiveTab("violations")}
      />
      <ToolbarTab
        label="Rules"
        active={activeTab === "rules"}
        onClick={() => setActiveTab("rules")}
      />
    </>
  );

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold">Compliance</h1>
          {violations && violations.length > 0 && (
            <div className="flex items-center gap-2">
              {blockCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[var(--destructive-muted)] px-2.5 py-0.5 text-xs font-medium text-[var(--destructive)]">
                  <ShieldAlert className="h-3 w-3" />
                  {blockCount} block{blockCount !== 1 ? "s" : ""}
                </span>
              )}
              {warningCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[var(--warning-muted)] px-2.5 py-0.5 text-xs font-medium text-[var(--warning)]">
                  <Shield className="h-3 w-3" />
                  {warningCount} warning{warningCount !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          )}
        </div>
        {portfolios && (
          <PortfolioSelector
            portfolios={portfolios}
            value={activePortfolioId}
            onChange={(id) => {
              setSelectedPortfolioId(id);
              setSelectedViolationId(null);
            }}
          />
        )}
      </div>

      {/* Dashboard Tab — CCO Analytics View */}
      {activeTab === "dashboard" && (
        <SectionPanel title="Compliance Officer Dashboard" tabs={tabs}>
          <div className="p-3 space-y-3">
            {/* KPI Strip */}
            <div className="grid grid-cols-5 gap-3">
              <KpiTile
                label="Total Violations"
                value={String(violations?.length ?? 0)}
                color={
                  violations && violations.length > 0 ? "var(--destructive)" : "var(--success)"
                }
              />
              <KpiTile label="Blocks" value={String(blockCount)} color="var(--destructive)" />
              <KpiTile label="Warnings" value={String(warningCount)} color="var(--warning)" />
              <KpiTile label="Breaches" value={String(breachCount)} color="var(--accent-orange)" />
              <KpiTile
                label="Compliance Rate"
                value={
                  violations && violations.length > 0
                    ? `${((1 - violations.length / Math.max(violations.length + 10, 1)) * 100).toFixed(1)}%`
                    : "100%"
                }
                color="var(--success)"
              />
            </div>

            {/* Charts row: Donut + Violation breakdown by rule */}
            <div className="grid grid-cols-12 gap-3">
              {/* Donut: Violations by Severity */}
              <div className="col-span-5 rounded-md border border-[var(--border)] bg-[var(--card)] p-3">
                <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Violations by Severity
                </p>
                {violations && violations.length > 0 ? (
                  <DonutChart
                    segments={[
                      ...(blockCount > 0
                        ? [{ label: "Blocks", value: blockCount, color: "var(--destructive)" }]
                        : []),
                      ...(warningCount > 0
                        ? [{ label: "Warnings", value: warningCount, color: "var(--warning)" }]
                        : []),
                      ...(breachCount > 0
                        ? [{ label: "Breaches", value: breachCount, color: "var(--accent-orange)" }]
                        : []),
                    ]}
                    centerValue={String(violations.length)}
                    centerLabel="Total"
                    size={160}
                    thickness={28}
                  />
                ) : (
                  <div className="flex flex-col items-center gap-2 py-6">
                    <ShieldCheck className="h-8 w-8 text-[var(--success)]" />
                    <p className="text-xs text-[var(--success)]">All clear</p>
                  </div>
                )}
              </div>

              {/* Violations by Rule — breakdown table */}
              <div className="col-span-7 rounded-md border border-[var(--border)] bg-[var(--card)]">
                <div className="border-b border-[var(--border)] bg-[var(--primary-muted)] px-3 py-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--foreground)]">
                    Violations by Rule
                  </span>
                </div>
                <ViolationsByRule violations={violations ?? []} fundSlug={fundSlug} />
              </div>
            </div>

            {/* Recent violations list — quick glance */}
            {violations && violations.length > 0 && (
              <div className="rounded-md border border-[var(--border)] bg-[var(--card)]">
                <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--primary-muted)] px-3 py-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--foreground)]">
                    Recent Violations
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveTab("violations")}
                    className="text-[10px] text-[var(--primary)] hover:underline"
                  >
                    View all &rarr;
                  </button>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
                      <th className="px-3 py-1.5 font-medium">Severity</th>
                      <th className="px-3 py-1.5 font-medium">Rule</th>
                      <th className="px-3 py-1.5 font-medium">Message</th>
                      <th className="px-3 py-1.5 font-medium text-right">Detected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {violations.slice(0, 8).map((v) => (
                      <tr
                        key={v.id}
                        className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
                      >
                        <td className="px-3 py-1.5">
                          <span
                            className={cn(
                              "inline-block rounded-full px-2 py-0.5 text-[10px] font-medium",
                              SEVERITY_BADGE[v.severity] ?? "",
                            )}
                          >
                            {v.severity}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-xs font-medium">{v.rule_name}</td>
                        <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)] max-w-[300px] truncate">
                          {v.message}
                        </td>
                        <td className="px-3 py-1.5 text-right text-xs text-[var(--muted-foreground)]">
                          {new Date(v.detected_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </SectionPanel>
      )}

      {/* Violations Tab */}
      {activeTab === "violations" && (
        <SectionPanel title="Compliance Officer Dashboard" tabs={tabs}>
          <div className="p-3">
            <div className="flex gap-3">
              {/* Left: Violations list */}
              <div className="min-w-0 flex-1 space-y-3">
                {/* Toolbar */}
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-1.5">
                    {(["all", "block", "warning", "breach"] as const).map((sev) => (
                      <button
                        key={sev}
                        type="button"
                        onClick={() => setSeverityFilter(sev)}
                        className={cn(
                          "rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors",
                          severityFilter === sev
                            ? sev === "all"
                              ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                              : SEVERITY_BADGE[sev]
                            : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
                        )}
                      >
                        {sev}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={handleExport}
                    title="Export to CSV"
                    className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 text-xs text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
                  >
                    <Download className="h-3.5 w-3.5" />
                    CSV
                  </button>
                </div>

                {/* Violations list */}
                {isLoading ? (
                  <p className="text-sm text-[var(--muted-foreground)]">Loading violations...</p>
                ) : !filteredViolations.length ? (
                  <div className="flex flex-col items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-12">
                    <ShieldCheck className="h-8 w-8 text-[var(--success)]" />
                    <p className="text-sm text-[var(--muted-foreground)]">No active violations</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {filteredViolations.map((v) => (
                      <button
                        key={v.id}
                        type="button"
                        onClick={() => {
                          setSelectedViolationId(v.id);
                          setWaiveReason("");
                        }}
                        className={cn(
                          "flex w-full items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                          selectedViolationId === v.id
                            ? "border-[var(--primary)] bg-[var(--primary-muted)]"
                            : "border-transparent hover:bg-[var(--muted)]",
                        )}
                      >
                        <StatusDot variant={severityDotVariant(v.severity)} size={8} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-[var(--foreground)]">
                              {v.rule_name}
                            </span>
                            <span
                              className={cn(
                                "inline-block rounded-full px-2 py-0.5 text-[10px] font-medium",
                                SEVERITY_BADGE[v.severity] ?? "",
                              )}
                            >
                              {v.severity}
                            </span>
                          </div>
                          <p className="mt-0.5 truncate text-xs text-[var(--muted-foreground)]">
                            {v.message}
                          </p>
                          <p className="mt-0.5 text-[10px] text-[var(--muted-foreground)]">
                            {new Date(v.detected_at).toLocaleString()}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Remediation */}
                {activePortfolioId && (
                  <div className="mt-4">
                    <RemediationPanel portfolioId={activePortfolioId} fundSlug={fundSlug} />
                  </div>
                )}
              </div>

              {/* Right: Stacked alert cards */}
              <div
                className="hidden w-[400px] shrink-0 space-y-2 overflow-y-auto lg:block"
                style={{ maxHeight: "calc(100vh - 16rem)" }}
              >
                <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                  Alerts ({filteredViolations.length})
                </p>
                {filteredViolations.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-[var(--border)] bg-[var(--card)] px-4 py-16">
                    <ShieldCheck className="h-8 w-8 text-[var(--success)]" />
                    <p className="text-sm text-[var(--muted-foreground)]">All clear</p>
                  </div>
                ) : (
                  filteredViolations.map((v) => {
                    const isExpanded = selectedViolationId === v.id;
                    return (
                      <div
                        key={v.id}
                        className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)] transition-colors"
                      >
                        {/* Colored severity header bar */}
                        <div
                          className={cn(
                            "px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider",
                            v.severity === "block"
                              ? "bg-[var(--destructive)] text-white"
                              : v.severity === "warning"
                                ? "bg-[var(--warning)] text-black"
                                : "bg-[var(--accent-orange)] text-white",
                          )}
                        >
                          {v.severity === "block"
                            ? "Compliance Check Failed"
                            : v.severity === "warning"
                              ? "Compliance Warning"
                              : "Compliance Breach"}
                        </div>

                        <button
                          type="button"
                          onClick={() => {
                            setSelectedViolationId(isExpanded ? null : v.id);
                            setWaiveReason("");
                          }}
                          className="flex w-full items-start gap-3 px-3 py-2.5 text-left"
                        >
                          <div className="min-w-0 flex-1">
                            <span className="text-xs font-semibold text-[var(--foreground)]">
                              {v.rule_name}
                            </span>
                            <p className="mt-0.5 text-[11px] text-[var(--muted-foreground)]">
                              {v.message}
                            </p>
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="border-t border-[var(--border)] px-3 py-2.5 space-y-2.5">
                            {(v.current_value || v.limit_value) && (
                              <div className="flex gap-3 text-xs">
                                {v.current_value && (
                                  <div>
                                    <p className="text-[10px] text-[var(--muted-foreground)]">
                                      Current
                                    </p>
                                    <p className="font-mono font-semibold text-[var(--destructive)]">
                                      {v.current_value}
                                    </p>
                                  </div>
                                )}
                                {v.limit_value && (
                                  <div>
                                    <p className="text-[10px] text-[var(--muted-foreground)]">
                                      Limit
                                    </p>
                                    <p className="font-mono font-semibold">{v.limit_value}</p>
                                  </div>
                                )}
                              </div>
                            )}

                            <p className="text-[10px] text-[var(--muted-foreground)]">
                              Detected: {new Date(v.detected_at).toLocaleString()}
                              {v.deadline_at &&
                                ` — Deadline: ${new Date(v.deadline_at).toLocaleString()}`}
                            </p>

                            {canWrite && (
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => resolveMutation.mutate(v.id)}
                                  disabled={resolveMutation.isPending}
                                  title="Approve / Resolve"
                                  className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--success)] text-white transition-opacity hover:opacity-80 disabled:opacity-50"
                                >
                                  &#10003;
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (waiveReason.trim()) {
                                      waiveMutation.mutate({
                                        violationId: v.id,
                                        reason: waiveReason,
                                      });
                                    }
                                  }}
                                  disabled={!waiveReason.trim() || waiveMutation.isPending}
                                  title="Waive"
                                  className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--warning)] text-black transition-opacity hover:opacity-80 disabled:opacity-50"
                                >
                                  &#8943;
                                </button>
                                <Link
                                  href={`/${fundSlug}/portfolio/${v.portfolio_id}?tab=positions`}
                                  title="View Portfolio"
                                  className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--border)] text-xs text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)]"
                                >
                                  &#8594;
                                </Link>
                                <input
                                  type="text"
                                  value={waiveReason}
                                  onChange={(e) => setWaiveReason(e.target.value)}
                                  placeholder="Waiver reason..."
                                  className="ml-1 flex-1 rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-[11px] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                                />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </SectionPanel>
      )}

      {/* Rules Tab */}
      {activeTab === "rules" && (
        <SectionPanel title="Compliance Officer Dashboard" tabs={tabs}>
          <div className="p-3">
            <RuleTable />
          </div>
        </SectionPanel>
      )}
    </div>
  );
}

// ─── CCO Dashboard Sub-components ──────────────────────────

function KpiTile({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-center">
      <p className="font-mono text-xl font-bold" style={color ? { color } : undefined}>
        {value}
      </p>
      <p className="mt-0.5 text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
        {label}
      </p>
    </div>
  );
}

function ViolationsByRule({
  violations,
  fundSlug: _fundSlug,
}: {
  violations: Violation[];
  fundSlug: string;
}) {
  const grouped = useMemo(() => {
    const map = new Map<string, { count: number; severity: string }>();
    for (const v of violations) {
      const existing = map.get(v.rule_name);
      if (existing) {
        existing.count++;
      } else {
        map.set(v.rule_name, { count: 1, severity: v.severity });
      }
    }
    return Array.from(map.entries())
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, 10);
  }, [violations]);

  if (grouped.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 px-3 py-8">
        <ShieldCheck className="h-6 w-6 text-[var(--success)]" />
        <p className="text-xs text-[var(--muted-foreground)]">No violations</p>
      </div>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
          <th className="px-3 py-1.5 font-medium">Rule</th>
          <th className="px-3 py-1.5 font-medium">Severity</th>
          <th className="px-3 py-1.5 font-medium text-right">Count</th>
          <th className="px-3 py-1.5" />
        </tr>
      </thead>
      <tbody>
        {grouped.map(([ruleName, { count, severity }]) => (
          <tr
            key={ruleName}
            className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
          >
            <td className="px-3 py-1.5 text-xs font-medium">{ruleName}</td>
            <td className="px-3 py-1.5">
              <span
                className={cn(
                  "inline-block rounded-full px-2 py-0.5 text-[10px] font-medium",
                  SEVERITY_BADGE[severity] ?? "",
                )}
              >
                {severity}
              </span>
            </td>
            <td className="px-3 py-1.5 text-right font-mono text-xs font-semibold">{count}</td>
            <td className="px-3 py-1.5 text-right">
              {/* Visual bar showing relative count */}
              <div
                className="inline-block h-2 rounded-full"
                style={{
                  width: `${Math.max((count / Math.max(...violations.map(() => 1), 1)) * 60, 8)}px`,
                  backgroundColor:
                    severity === "block"
                      ? "var(--destructive)"
                      : severity === "warning"
                        ? "var(--warning)"
                        : "var(--accent-orange)",
                  opacity: 0.6,
                }}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
