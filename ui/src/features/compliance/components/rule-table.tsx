"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";
import { rulesQueryOptions, updateRule } from "../api";
import type { RuleDefinition } from "../types";
import { RuleFormDialog } from "./rule-form-dialog";

const SEVERITY_BADGE: Record<string, string> = {
  block: "bg-red-100 text-red-800",
  warning: "bg-yellow-100 text-yellow-800",
  breach: "bg-orange-100 text-orange-800",
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
      {canWrite && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={openCreate}
            className="rounded-md bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90"
          >
            + Add Rule
          </button>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
              <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                Name
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                Type
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                Severity
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                Parameters
              </th>
              <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                Active
              </th>
              {canWrite && (
                <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {(!rules || rules.length === 0) && (
              <tr>
                <td
                  colSpan={canWrite ? 6 : 5}
                  className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                >
                  No compliance rules configured.
                </td>
              </tr>
            )}
            {rules?.map((rule) => (
              <tr key={rule.id} className="border-b border-[var(--border)] last:border-b-0">
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
                      rule.is_active ? "bg-green-500" : "bg-gray-300"
                    } ${!canWrite ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
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
            ))}
          </tbody>
        </table>
      </div>

      {showDialog && <RuleFormDialog rule={dialogRule} onClose={closeDialog} />}
    </>
  );
}
