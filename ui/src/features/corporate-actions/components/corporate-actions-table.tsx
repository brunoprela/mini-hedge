"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { corporateActionsQueryOptions } from "../api";
import type { ActionType, ProcessedAction, ProcessingStatus } from "../types";

const STATUS_COLORS: Record<ProcessingStatus, string> = {
  PROCESSED: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  PENDING: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  FAILED: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  SKIPPED: "bg-zinc-100 text-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400",
};

const ACTION_TYPE_COLORS: Record<ActionType, string> = {
  DIVIDEND: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  STOCK_SPLIT: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  REVERSE_SPLIT: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  SPINOFF: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
};

function formatCurrency(value: number) {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function CorporateActionsTable() {
  const { fundSlug } = useFundContext();
  const { data: actions, isLoading } = useQuery(corporateActionsQueryOptions(fundSlug));
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading corporate actions...</div>;
  }

  if (!actions || actions.length === 0) {
    return <div className="text-sm text-[var(--muted-foreground)]">No corporate actions found.</div>;
  }

  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-[var(--muted-foreground)]">
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider" />
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider">Date</th>
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider">Instrument</th>
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider">Type</th>
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider">Status</th>
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider">Description</th>
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider">Adjustments</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action) => {
            const isExpanded = expandedId === action.id;
            return (
              <TableRow
                key={action.id}
                action={action}
                isExpanded={isExpanded}
                onToggle={() => setExpandedId(isExpanded ? null : action.id)}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TableRow({
  action,
  isExpanded,
  onToggle,
}: {
  action: ProcessedAction;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const adjustmentSummary = summarizeAdjustments(action);

  return (
    <>
      <tr className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]">
        <td className="px-3 py-2">
          {action.adjustments.length > 0 && (
            <button
              type="button"
              onClick={onToggle}
              className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            >
              {isExpanded ? "\u25BC" : "\u25B6"}
            </button>
          )}
        </td>
        <td className="px-3 py-2 font-mono text-xs">
          {action.ex_date}
        </td>
        <td className="px-3 py-1 font-medium">
          {action.instrument_id}
        </td>
        <td className="px-3 py-2">
          <span
            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${ACTION_TYPE_COLORS[action.action_type]}`}
          >
            {action.action_type.replace("_", " ")}
          </span>
        </td>
        <td className="px-3 py-2">
          <span
            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[action.status]}`}
          >
            {action.status}
          </span>
        </td>
        <td className="px-3 py-2 text-[var(--muted-foreground)]">
          {action.description}
        </td>
        <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
          {adjustmentSummary}
        </td>
      </tr>
      {isExpanded && action.adjustments.length > 0 && (
        <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
          <td colSpan={7} className="px-6 py-3">
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Adjustment Details
              </p>
              <div className="overflow-x-auto rounded-md border border-[var(--border)]">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--table-border)] text-left text-[var(--muted-foreground)]">
                      <th className="px-3 py-1.5 text-xs font-medium">#</th>
                      <th className="px-3 py-1.5 text-xs font-medium">Quantity Delta</th>
                      <th className="px-3 py-1.5 text-xs font-medium">Cost Basis Adj.</th>
                      <th className="px-3 py-1.5 text-xs font-medium">Cash Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {action.adjustments.map((adj, idx) => (
                      <tr
                        key={idx}
                        className="border-b border-[var(--table-border)] last:border-0"
                      >
                        <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                          {idx + 1}
                        </td>
                        <td className="px-3 py-1.5 font-mono text-xs">
                          <span className={adj.quantity_delta >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}>
                            {adj.quantity_delta >= 0 ? "+" : ""}
                            {adj.quantity_delta.toLocaleString()}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 font-mono text-xs">
                          {formatCurrency(adj.cost_basis_adjustment)}
                        </td>
                        <td className="px-3 py-1.5 font-mono text-xs">
                          {formatCurrency(adj.cash_amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function summarizeAdjustments(action: ProcessedAction): string {
  if (action.adjustments.length === 0) return "\u2014";

  const totalQty = action.adjustments.reduce((sum, a) => sum + a.quantity_delta, 0);
  const totalCash = action.adjustments.reduce((sum, a) => sum + a.cash_amount, 0);

  const parts: string[] = [];
  if (totalQty !== 0) parts.push(`qty: ${totalQty >= 0 ? "+" : ""}${totalQty.toLocaleString()}`);
  if (totalCash !== 0) parts.push(`cash: ${formatCurrency(totalCash)}`);

  return parts.length > 0 ? parts.join(", ") : `${action.adjustments.length} adj.`;
}
