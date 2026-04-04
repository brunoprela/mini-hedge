"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { useTableState } from "@/shared/hooks/use-table-state";
import { Permission } from "@/shared/lib/permissions";
import { rulesQueryOptions, updateRule } from "../api";
import type { RuleDefinition } from "../types";
import { RuleFormDialog } from "./rule-form-dialog";

const SEVERITY_BADGE: Record<string, string> = {
  block: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
  warning: "bg-[var(--warning-muted)] text-[var(--warning)]",
  breach: "bg-[var(--accent-orange-muted)] text-[var(--accent-orange)]",
};

function formatRuleType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatParameters(ruleType: string, params: Record<string, unknown>): string {
  switch (ruleType) {
    case "concentration_limit":
      return `Max ${params.max_pct}% per name`;
    case "sector_limit":
      return params.sector
        ? `${params.sector} \u2264 ${params.max_pct}%`
        : `Sector \u2264 ${params.max_pct}%`;
    case "country_limit":
      return params.country
        ? `${params.country} \u2264 ${params.max_pct}%`
        : `Country \u2264 ${params.max_pct}%`;
    case "restricted_list": {
      const tickers = params.restricted_instruments as string[];
      if (!tickers || tickers.length === 0) return "No restrictions";
      return `Restricted: ${tickers.slice(0, 5).join(", ")}${tickers.length > 5 ? ` +${tickers.length - 5}` : ""}`;
    }
    case "short_selling":
      return params.allow_short ? "Shorts: allowed" : "Shorts: not allowed";
    default:
      return JSON.stringify(params);
  }
}

export function RuleTable() {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const queryClient = useQueryClient();
  const { data: rules, isLoading } = useQuery(rulesQueryOptions(fundSlug));

  const [dialogRule, setDialogRule] = useState<RuleDefinition | undefined>();
  const [showDialog, setShowDialog] = useState(false);

  const canWrite = can(Permission.COMPLIANCE_WRITE);

  const table = useTableState<Record<string, unknown>>({
    data: (rules ?? []) as unknown as Record<string, unknown>[],
    initialSort: { key: "name", direction: "asc" },
    pageSize: 20,
    searchKeys: ["name", "rule_type", "severity"],
  });

  const toggleMutation = useMutation({
    mutationFn: (rule: RuleDefinition) =>
      updateRule(fundSlug, rule.id, { is_active: !rule.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance-rules"] });
      toast.success("Rule updated");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  function openCreate() {
    setDialogRule(undefined);
    setShowDialog(true);
  }

  function openEdit(rule: RuleDefinition) {
    setDialogRule(rule);
    setShowDialog(true);
  }

  function closeDialog() {
    setShowDialog(false);
    setDialogRule(undefined);
  }

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading rules...</p>;
  }

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <div className="w-72">
          <TableSearch
            value={table.search}
            onChange={table.setSearch}
            placeholder="Search rules..."
          />
        </div>
        {canWrite && (
          <button
            type="button"
            onClick={openCreate}
            className="rounded-md bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90"
          >
            + Add Rule
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
              <SortableHeader<keyof Record<string, unknown>>
                label="Name"
                sortKey="name"
                currentSort={table.sortKey as string | null}
                direction={table.sortDirection}
                onSort={(key) => table.onSort(key)}
              />
              <SortableHeader<keyof Record<string, unknown>>
                label="Type"
                sortKey="rule_type"
                currentSort={table.sortKey as string | null}
                direction={table.sortDirection}
                onSort={(key) => table.onSort(key)}
                info="The compliance check category"
              />
              <SortableHeader<keyof Record<string, unknown>>
                label="Severity"
                sortKey="severity"
                currentSort={table.sortKey as string | null}
                direction={table.sortDirection}
                onSort={(key) => table.onSort(key)}
                info="Block = prevents trades, Warning = alert only, Breach = requires cure"
              />
              <SortableHeader<keyof Record<string, unknown>>
                label="Parameters"
                sortKey="parameters"
                currentSort={table.sortKey as string | null}
                direction={table.sortDirection}
                onSort={(key) => table.onSort(key)}
                info="Rule-specific thresholds and configuration"
              />
              <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Active
              </th>
              {canWrite && (
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {table.rows.length === 0 && (
              <tr>
                <td
                  colSpan={canWrite ? 6 : 5}
                  className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                >
                  No compliance rules configured.
                </td>
              </tr>
            )}
            {table.rows.map((row) => {
              const rule = row as unknown as RuleDefinition;
              return (
                <tr
                  key={rule.id}
                  className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-4 py-3 font-medium">{rule.name}</td>
                  <td className="px-4 py-3">{formatRuleType(rule.rule_type)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_BADGE[rule.severity] ?? ""}`}
                    >
                      {rule.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--muted-foreground)]">
                    {formatParameters(rule.rule_type, rule.parameters)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      disabled={!canWrite || toggleMutation.isPending}
                      onClick={() => toggleMutation.mutate(rule)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        rule.is_active ? "bg-[var(--success)]" : "bg-[var(--border-bright)]"
                      } ${!canWrite ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 rounded-full bg-[var(--card)] transition-transform ${
                          rule.is_active ? "translate-x-4.5" : "translate-x-0.5"
                        }`}
                      />
                    </button>
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => openEdit(rule)}
                        className="text-sm text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
                      >
                        Edit
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {table.totalPages > 1 && (
        <TablePagination
          page={table.page}
          totalPages={table.totalPages}
          totalItems={table.totalFiltered}
          pageSize={table.pageSize}
          onPageChange={table.setPage}
        />
      )}

      {showDialog && <RuleFormDialog rule={dialogRule} onClose={closeDialog} />}
    </>
  );
}
