"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTableState } from "@/shared/hooks/use-table-state";
import { clientFetch } from "@/shared/lib/api";
import { Permission } from "@/shared/lib/permissions";
import { violationsQueryOptions } from "../api";
import type { Violation } from "../types";

const SEVERITY_BADGE: Record<string, string> = {
  block: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
  warning: "bg-[var(--warning-muted)] text-[var(--warning)]",
  breach: "bg-[var(--accent-orange-muted)] text-[var(--accent-orange)]",
};

const SEVERITY_PILL: Record<string, { active: string; inactive: string }> = {
  all: {
    active: "bg-[var(--primary)] text-[var(--primary-foreground)]",
    inactive: "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
  },
  block: {
    active: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
    inactive: "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
  },
  warning: {
    active: "bg-[var(--warning-muted)] text-[var(--warning)]",
    inactive: "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
  },
  breach: {
    active: "bg-[var(--accent-orange-muted)] text-[var(--accent-orange)]",
    inactive: "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
  },
};

type SeverityFilter = "all" | "block" | "warning" | "breach";

export function ViolationsPanel({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const queryClient = useQueryClient();
  const { data: violations, isLoading } = useQuery(violationsQueryOptions(fundSlug, portfolioId));

  const canWrite = can(Permission.COMPLIANCE_WRITE);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const exportCSV = useExportCSV();

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
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const filteredViolations = useMemo(() => {
    if (!violations) return [];
    if (severityFilter === "all") return violations;
    return violations.filter((v) => v.severity === severityFilter);
  }, [violations, severityFilter]);

  const table = useTableState<Record<string, unknown>>({
    data: filteredViolations as unknown as Record<string, unknown>[],
    initialSort: { key: "detected_at", direction: "desc" },
    pageSize: 15,
    searchKeys: ["rule_name", "message"],
  });

  const handleExport = () => {
    if (!filteredViolations || filteredViolations.length === 0) return;
    const exportData = filteredViolations.map((v) => ({
      rule: v.rule_name,
      severity: v.severity,
      message: v.message,
      portfolio_id: v.portfolio_id,
      detected_at: v.detected_at,
    }));
    exportCSV(exportData as unknown as Record<string, unknown>[], `violations-${portfolioId}`);
  };

  const handleResolveAll = () => {
    for (const row of table.rows) {
      resolveMutation.mutate(row.id as string);
    }
  };

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading violations...</p>;
  }

  if (!violations || violations.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No active violations.</p>;
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Severity filter pills */}
        <div className="flex items-center gap-1.5">
          {(["all", "block", "warning", "breach"] as const).map((sev) => {
            const isActive = severityFilter === sev;
            const styles = SEVERITY_PILL[sev];
            return (
              <button
                key={sev}
                type="button"
                onClick={() => setSeverityFilter(sev)}
                className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
                  isActive ? styles.active : styles.inactive
                }`}
              >
                {sev === "all" ? "All" : sev}
              </button>
            );
          })}
        </div>

        {/* Search + Export + Resolve All */}
        <div className="flex items-center gap-2">
          <TableSearch
            value={table.search}
            onChange={table.setSearch}
            placeholder="Search violations..."
          />
          <button
            type="button"
            onClick={handleExport}
            title="Export to CSV"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
          {canWrite && table.rows.length > 0 && (
            <button
              type="button"
              onClick={handleResolveAll}
              disabled={resolveMutation.isPending}
              className="shrink-0 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--accent)] transition-colors disabled:opacity-50"
            >
              Resolve All
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
              <SortableHeader
                label="Rule"
                sortKey="rule_name"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Severity"
                sortKey="severity"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Message"
                sortKey="message"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Detected"
                sortKey="detected_at"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                View
              </th>
              {canWrite && (
                <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => {
              const v = row as unknown as Violation;
              return (
                <tr
                  key={v.id}
                  className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-4 py-3 font-medium">{v.rule_name}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_BADGE[v.severity] ?? ""}`}
                    >
                      {v.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--muted-foreground)]">{v.message}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted-foreground)]">
                    {new Date(v.detected_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/${fundSlug}/portfolio/${v.portfolio_id}#positions`}
                      className="text-[var(--foreground)] underline-offset-2 hover:underline"
                    >
                      View &rarr;
                    </Link>
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => resolveMutation.mutate(v.id)}
                        disabled={resolveMutation.isPending}
                        className="text-sm text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
                      >
                        Resolve
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {table.totalPages > 1 && (
        <TablePagination
          page={table.page}
          totalPages={table.totalPages}
          totalItems={table.totalFiltered}
          pageSize={table.pageSize}
          onPageChange={table.setPage}
        />
      )}
    </div>
  );
}
