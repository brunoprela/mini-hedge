"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronRight, Download, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { ViolationDetailPanel } from "./violation-detail-panel";
import { ViolationTimeline } from "./violation-timeline";
import { toast } from "sonner";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTableState } from "@/shared/hooks/use-table-state";
import { api, fundHeaders } from "@/shared/lib/api-client";
import { Permission } from "@/shared/lib/permissions";
import { violationsQueryOptions, waiveViolation } from "../api";
import type { Violation } from "../types";

function isActionable(v: Violation): boolean {
  return !v.resolved_at;
}

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
  const [waiveTarget, setWaiveTarget] = useState<string | null>(null);
  const [waiveReason, setWaiveReason] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkWaiveOpen, setBulkWaiveOpen] = useState(false);
  const [bulkWaiveReason, setBulkWaiveReason] = useState("");
  const exportCSV = useExportCSV();

  const resolveMutation = useMutation({
    mutationFn: async (violationId: string) => {
      const { data, error } = await api.POST(
        "/api/v1/compliance/violations/{violation_id}/resolve",
        {
          params: { path: { violation_id: violationId } },
          body: { resolved_by: "current_user" } as never,
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data as Violation;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
      toast.success("Violation resolved");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const waiveMutation = useMutation({
    mutationFn: ({ violationId, reason }: { violationId: string; reason: string }) =>
      waiveViolation(fundSlug, violationId, { waived_by: "current_user", reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
      toast.success("Violation waived");
      setWaiveTarget(null);
      setWaiveReason("");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const bulkResolveMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.all(
        ids.map(async (id) => {
          const { error } = await api.POST(
            "/api/v1/compliance/violations/{violation_id}/resolve",
            {
              params: { path: { violation_id: id } },
              body: { resolved_by: "current_user" } as never,
              headers: fundHeaders(fundSlug),
            },
          );
          if (error) throw error;
        }),
      );
    },
    onSuccess: (_data, ids) => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
      toast.success(`${ids.length} violation(s) resolved`);
      setSelectedIds(new Set());
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const bulkWaiveMutation = useMutation({
    mutationFn: async ({ ids, reason }: { ids: string[]; reason: string }) => {
      await Promise.all(
        ids.map((id) => waiveViolation(fundSlug, id, { waived_by: "current_user", reason })),
      );
    },
    onSuccess: (_data, { ids }) => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
      toast.success(`${ids.length} violation(s) waived`);
      setSelectedIds(new Set());
      setBulkWaiveOpen(false);
      setBulkWaiveReason("");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

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

  const actionableRows = useMemo(
    () => (table.rows as unknown as Violation[]).filter(isActionable),
    [table.rows],
  );

  const allActionableSelected =
    actionableRows.length > 0 && actionableRows.every((v) => selectedIds.has(v.id));

  const someSelected = selectedIds.size > 0;

  const selectedViolation = useMemo(
    () => (selectedId ? (violations ?? []).find((v) => v.id === selectedId) ?? null : null),
    [violations, selectedId],
  );

  const toggleSelectAll = useCallback(() => {
    if (allActionableSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(actionableRows.map((v) => v.id)));
    }
  }, [allActionableSelected, actionableRows]);

  const handleBulkResolve = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    bulkResolveMutation.mutate(ids);
  };

  const handleBulkWaive = () => {
    setBulkWaiveOpen(true);
  };

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
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
          {canWrite && table.rows.length > 0 && (
            <button
              type="button"
              onClick={handleResolveAll}
              disabled={resolveMutation.isPending}
              className="shrink-0 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--accent)] transition-colors disabled:opacity-50"
            >
              Resolve All
            </button>
          )}
        </div>
      </div>

      {/* Master-detail layout */}
      <div className="flex gap-3">
      {/* Table */}
      <div className="min-w-0 flex-1 overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
        <table className="min-w-full divide-y divide-[var(--border)] text-sm">
          <thead>
            <tr>
              {canWrite && (
                <th className="w-10 px-3 py-1.5">
                  <input
                    type="checkbox"
                    checked={allActionableSelected}
                    onChange={toggleSelectAll}
                    className="h-3.5 w-3.5 rounded border-(--border) accent-(--primary) cursor-pointer"
                    title="Select all actionable violations"
                  />
                </th>
              )}
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
              <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                View
              </th>
              {canWrite && (
                <th className="px-3 py-1.5 text-left font-medium text-[var(--muted-foreground)]">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {table.rows.map((row) => {
              const v = row as unknown as Violation;
              const isExpanded = expandedId === v.id;
              const isSelected = selectedId === v.id;
              return (
                <tr
                  key={v.id}
                  className={`transition-colors hover:bg-[var(--table-row-hover)] cursor-pointer ${isSelected ? "bg-[var(--accent)]" : ""}`}
                  onClick={() => {
                    setExpandedId(isExpanded ? null : v.id);
                    setSelectedId(v.id);
                  }}
                >
                  {canWrite && (
                    <td className="px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                      {isActionable(v) ? (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(v.id)}
                          onChange={() => toggleSelected(v.id)}
                          className="h-3.5 w-3.5 rounded border-(--border) accent-(--primary) cursor-pointer"
                        />
                      ) : (
                        <span className="inline-block h-3.5 w-3.5" />
                      )}
                    </td>
                  )}
                  <td className="px-3 py-1.5 font-medium">
                    <span className="inline-flex items-center gap-1">
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
                      )}
                      {v.rule_name}
                    </span>
                  </td>
                  <td className="px-3 py-1.5">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_BADGE[v.severity] ?? ""}`}
                    >
                      {v.severity}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-[var(--muted-foreground)]">{v.message}</td>
                  <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                    {new Date(v.detected_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-1.5">
                    <Link
                      href={`/${fundSlug}/portfolio/${v.portfolio_id}#positions`}
                      className="text-[var(--foreground)] underline-offset-2 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View &rarr;
                    </Link>
                  </td>
                  {canWrite && (
                    <td className="px-3 py-1.5">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          resolveMutation.mutate(v.id);
                        }}
                        disabled={resolveMutation.isPending}
                        className="text-sm text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
                      >
                        Resolve
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setWaiveTarget(v.id);
                        }}
                        className="text-sm text-[var(--muted-foreground)] underline hover:text-[var(--foreground)] ml-2"
                      >
                        Waive
                      </button>
                    </td>
                  )}
                </tr>
              );
              /* Timeline detail row rendered via sibling fragment —
                 React doesn't allow fragments as direct tbody children,
                 so we use a second <tr> below via a wrapper pattern. */
            }).flatMap((rowEl, _i) => {
              const v = table.rows[_i] as unknown as Violation;
              const isExpanded = expandedId === v.id;
              const colCount = canWrite ? 8 : 5;
              return [
                rowEl,
                isExpanded && (
                  <tr key={`${v.id}-timeline`}>
                    <td colSpan={colCount} className="px-6 py-3 bg-[var(--muted)]/30">
                      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">
                        Violation Timeline
                      </p>
                      <ViolationTimeline violation={v} />
                    </td>
                  </tr>
                ),
              ];
            })}
          </tbody>
        </table>
      </div>

      {/* Detail panel */}
      {selectedViolation && (
        <ViolationDetailPanel
          violation={selectedViolation}
          onClose={() => setSelectedId(null)}
          canWrite={canWrite}
          onResolve={(id) => resolveMutation.mutate(id)}
          onWaive={(id) => setWaiveTarget(id)}
          isResolving={resolveMutation.isPending}
        />
      )}
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

      {/* Batch action bar */}
      {canWrite && someSelected && (
        <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2 flex items-center gap-3 rounded-lg border border-(--border) bg-(--card) px-4 py-2.5 shadow-lg">
          <span className="text-sm font-medium text-(--foreground)">
            {selectedIds.size} selected
          </span>
          <div className="h-4 w-px bg-(--border)" />
          <button
            type="button"
            onClick={handleBulkResolve}
            disabled={bulkResolveMutation.isPending || bulkWaiveMutation.isPending}
            className="inline-flex items-center gap-1.5 rounded-md bg-(--primary) px-3 py-1.5 text-sm font-medium text-(--primary-foreground) transition-colors hover:opacity-90 disabled:opacity-50"
          >
            <Check className="h-3.5 w-3.5" />
            {bulkResolveMutation.isPending ? "Resolving..." : "Resolve All"}
          </button>
          <button
            type="button"
            onClick={handleBulkWaive}
            disabled={bulkResolveMutation.isPending || bulkWaiveMutation.isPending}
            className="inline-flex items-center gap-1.5 rounded-md border border-(--border) bg-(--background) px-3 py-1.5 text-sm font-medium text-(--foreground) transition-colors hover:bg-(--accent) disabled:opacity-50"
          >
            Waive All
          </button>
          <button
            type="button"
            onClick={() => setSelectedIds(new Set())}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-(--muted-foreground) hover:text-(--foreground) transition-colors"
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </button>
        </div>
      )}

      {/* Bulk waive dialog */}
      {bulkWaiveOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-md border border-(--border) bg-(--card) p-6 shadow-xl">
            <h3 className="text-sm font-semibold">Waive {selectedIds.size} Violation(s)</h3>
            <p className="mt-1 text-sm text-(--muted-foreground)">
              Provide a reason for waiving the selected compliance violations.
            </p>
            <textarea
              value={bulkWaiveReason}
              onChange={(e) => setBulkWaiveReason(e.target.value)}
              placeholder="Reason for waiver..."
              rows={3}
              className="mt-3 w-full rounded-md border border-(--border) bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-(--primary)"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setBulkWaiveOpen(false);
                  setBulkWaiveReason("");
                }}
                className="rounded-lg px-3 py-1.5 text-sm text-(--muted-foreground) hover:text-(--foreground)"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  bulkWaiveMutation.mutate({
                    ids: Array.from(selectedIds),
                    reason: bulkWaiveReason,
                  })
                }
                disabled={!bulkWaiveReason.trim() || bulkWaiveMutation.isPending}
                className="rounded-lg bg-(--primary) px-3 py-1.5 text-sm font-medium text-(--primary-foreground) disabled:opacity-50"
              >
                {bulkWaiveMutation.isPending ? "Waiving..." : "Waive All"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Waive dialog */}
      {waiveTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl">
            <h3 className="text-sm font-semibold">Waive Violation</h3>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Provide a reason for waiving this compliance violation.
            </p>
            <textarea
              value={waiveReason}
              onChange={(e) => setWaiveReason(e.target.value)}
              placeholder="Reason for waiver..."
              rows={3}
              className="mt-3 w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setWaiveTarget(null);
                  setWaiveReason("");
                }}
                className="rounded-lg px-3 py-1.5 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  waiveMutation.mutate({ violationId: waiveTarget, reason: waiveReason })
                }
                disabled={!waiveReason.trim() || waiveMutation.isPending}
                className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
              >
                {waiveMutation.isPending ? "Waiving..." : "Waive"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
