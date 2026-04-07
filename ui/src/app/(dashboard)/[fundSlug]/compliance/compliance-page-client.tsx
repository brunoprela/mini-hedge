"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { RuleTable } from "@/features/compliance/components/rule-table";
import { RemediationPanel } from "@/features/compliance/components/remediation-panel";
import {
  rulesQueryOptions,
  violationsQueryOptions,
  waiveViolation,
} from "@/features/compliance/api";
import type { Violation } from "@/features/compliance/types";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { StatusDot } from "@/shared/components/charts";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";
import { clientFetch } from "@/shared/lib/api";
import { cn } from "@/shared/lib/cn";

type TabId = "violations" | "rules";

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
  const [activeTab, setActiveTab] = useState<TabId>("violations");
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

  const selectedViolation = useMemo(
    () => violations?.find((v) => v.id === selectedViolationId) ?? null,
    [violations, selectedViolationId],
  );

  const blockCount = violations?.filter((v) => v.severity === "block").length ?? 0;
  const warningCount = violations?.filter((v) => v.severity === "warning").length ?? 0;

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

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Compliance</h1>
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

        {/* Portfolio selector */}
        {portfolios && portfolios.length > 1 && (
          <select
            value={activePortfolioId}
            onChange={(e) => {
              setSelectedPortfolioId(e.target.value);
              setSelectedViolationId(null);
            }}
            className="rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {(
          [
            { id: "violations" as const, label: "Violations" },
            { id: "rules" as const, label: "Rules" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "rounded-t-lg px-4 py-2 text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "rules" ? (
        <RuleTable />
      ) : (
        <div className="flex gap-4">
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
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-xs text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
              >
                <Download className="h-3.5 w-3.5" />
                CSV
              </button>
            </div>

            {/* Violations list */}
            {isLoading ? (
              <p className="text-sm text-[var(--muted-foreground)]">Loading violations...</p>
            ) : !filteredViolations.length ? (
              <div className="flex flex-col items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-12">
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

          {/* Right: Detail panel */}
          <div className="hidden w-[380px] shrink-0 lg:block">
            {selectedViolation ? (
              <div className="sticky top-4 space-y-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                {/* Header */}
                <div>
                  <div className="flex items-center gap-2">
                    <StatusDot variant={severityDotVariant(selectedViolation.severity)} size={10} />
                    <h3 className="text-sm font-semibold text-[var(--foreground)]">
                      {selectedViolation.rule_name}
                    </h3>
                  </div>
                  <span
                    className={cn(
                      "mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium",
                      SEVERITY_BADGE[selectedViolation.severity] ?? "",
                    )}
                  >
                    {selectedViolation.severity}
                  </span>
                </div>

                {/* Message */}
                <div>
                  <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                    Description
                  </p>
                  <p className="mt-1 text-sm text-[var(--foreground)]">
                    {selectedViolation.message}
                  </p>
                </div>

                {/* Compliance check visual */}
                {(selectedViolation.current_value || selectedViolation.limit_value) && (
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                      Compliance Check
                    </p>
                    <div className="mt-2 grid grid-cols-2 gap-3">
                      {selectedViolation.current_value && (
                        <div>
                          <p className="text-[10px] text-[var(--muted-foreground)]">Current</p>
                          <p className="font-mono text-sm font-semibold text-[var(--destructive)]">
                            {selectedViolation.current_value}
                          </p>
                        </div>
                      )}
                      {selectedViolation.limit_value && (
                        <div>
                          <p className="text-[10px] text-[var(--muted-foreground)]">Limit</p>
                          <p className="font-mono text-sm font-semibold text-[var(--foreground)]">
                            {selectedViolation.limit_value}
                          </p>
                        </div>
                      )}
                    </div>
                    {selectedViolation.current_value && selectedViolation.limit_value && (
                      <div className="mt-2">
                        <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--muted)]">
                          <div
                            className="h-full rounded-full bg-[var(--destructive)] transition-all"
                            style={{
                              width: `${Math.min(
                                100,
                                (parseFloat(selectedViolation.current_value) /
                                  parseFloat(selectedViolation.limit_value)) *
                                  100,
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Metadata */}
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Detected</span>
                    <span className="text-[var(--foreground)]">
                      {new Date(selectedViolation.detected_at).toLocaleString()}
                    </span>
                  </div>
                  {selectedViolation.deadline_at && (
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Deadline</span>
                      <span className="text-[var(--foreground)]">
                        {new Date(selectedViolation.deadline_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Breach Type</span>
                    <span className="text-[var(--foreground)]">
                      {selectedViolation.breach_type}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                {canWrite && (
                  <div className="space-y-2 border-t border-[var(--border)] pt-3">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => resolveMutation.mutate(selectedViolation.id)}
                        disabled={resolveMutation.isPending}
                        className="flex-1 rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] transition-colors hover:opacity-90 disabled:opacity-50"
                      >
                        Resolve
                      </button>
                      <Link
                        href={`/${fundSlug}/portfolio/${selectedViolation.portfolio_id}?tab=positions`}
                        className="flex-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-center text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
                      >
                        View Portfolio
                      </Link>
                    </div>

                    {/* Waive section */}
                    <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3">
                      <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                        Waive Violation
                      </p>
                      <textarea
                        value={waiveReason}
                        onChange={(e) => setWaiveReason(e.target.value)}
                        placeholder="Reason for waiver..."
                        rows={2}
                        className="mt-2 w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          waiveMutation.mutate({
                            violationId: selectedViolation.id,
                            reason: waiveReason,
                          })
                        }
                        disabled={!waiveReason.trim() || waiveMutation.isPending}
                        className="mt-2 w-full rounded-lg border border-[var(--warning)] px-3 py-1.5 text-xs font-medium text-[var(--warning)] transition-colors hover:bg-[var(--warning-muted)] disabled:opacity-50"
                      >
                        {waiveMutation.isPending ? "Waiving..." : "Waive"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] px-4 py-16">
                <Shield className="h-8 w-8 text-[var(--muted-foreground)]" />
                <p className="text-sm text-[var(--muted-foreground)]">
                  Select a violation to view details
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
