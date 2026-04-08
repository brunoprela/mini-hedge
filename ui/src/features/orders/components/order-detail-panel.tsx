"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, Copy, FileText, X } from "lucide-react";
import Link from "next/link";
import { StatusDot } from "@/shared/components/charts";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { orderFillsQueryOptions } from "../api";
import type { OrderSummary } from "../types";
import { OrderStateBadge } from "./order-state-badge";

interface OrderDetailPanelProps {
  order: OrderSummary;
  onClose: () => void;
  onClone: (order: OrderSummary) => void;
}

export function OrderDetailPanel({ order, onClose, onClone }: OrderDetailPanelProps) {
  const { fundSlug } = useFundContext();

  const { data: fills } = useQuery({
    ...orderFillsQueryOptions(fundSlug, order.id),
    enabled: !!order.id,
  });

  const complianceResults = order.compliance_results as Record<string, unknown>[] | null;

  return (
    <div className="w-[340px] shrink-0 overflow-y-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold">{order.instrument_id}</span>
          <span
            className={`text-xs font-medium ${order.side === "buy" ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}
          >
            {order.side.toUpperCase()}
          </span>
          <OrderStateBadge state={order.state} />
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Order info */}
      <div className="space-y-3 p-3">
        {/* Key metrics */}
        <div className="grid grid-cols-2 gap-2">
          <DetailField label="Quantity" value={parseFloat(order.quantity).toLocaleString()} />
          <DetailField label="Filled" value={parseFloat(order.filled_quantity).toLocaleString()} />
          <DetailField
            label="Limit Price"
            value={order.limit_price ? `$${parseFloat(order.limit_price).toFixed(2)}` : "MKT"}
          />
          <DetailField
            label="Avg Fill"
            value={order.avg_fill_price ? `$${parseFloat(order.avg_fill_price).toFixed(2)}` : "—"}
          />
          <DetailField
            label="Type"
            value={`${order.order_type.toUpperCase()}${order.algo_type ? ` / ${order.algo_type.toUpperCase()}` : ""}`}
          />
          <DetailField label="TIF" value={order.time_in_force?.toUpperCase() ?? "—"} />
          {order.broker_id && <DetailField label="Broker" value={order.broker_id} />}
        </div>

        {/* Timestamps */}
        <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] p-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            <Clock className="h-3 w-3" />
            Timeline
          </div>
          <div className="space-y-1 text-xs">
            <TimelineRow label="Created" time={order.created_at} />
            {order.updated_at !== order.created_at && (
              <TimelineRow label="Updated" time={order.updated_at} />
            )}
          </div>
        </div>

        {/* Fills */}
        {fills && fills.length > 0 && (
          <div>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              Fills ({fills.length})
            </p>
            <div className="max-h-40 overflow-y-auto rounded-md border border-[var(--border)]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-[var(--muted-foreground)]">
                    <th className="px-2 py-1 font-medium">Qty</th>
                    <th className="px-2 py-1 font-medium">Price</th>
                    <th className="px-2 py-1 font-medium">Broker</th>
                    <th className="px-2 py-1 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {fills.map((f) => (
                    <tr key={f.id} className="border-b border-[var(--table-border)] last:border-0">
                      <td className="px-2 py-1 font-mono">
                        {parseFloat(f.quantity).toLocaleString()}
                      </td>
                      <td className="px-2 py-1 font-mono">${parseFloat(f.price).toFixed(2)}</td>
                      <td className="px-2 py-1 text-[var(--muted-foreground)]">
                        {f.broker_id ?? "—"}
                      </td>
                      <td className="px-2 py-1 text-[var(--muted-foreground)]">
                        {new Date(f.filled_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Compliance results */}
        {complianceResults && complianceResults.length > 0 && (
          <div>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              Compliance
            </p>
            <div className="space-y-1">
              {complianceResults.map((r, i) => (
                <div key={`cr-${r.rule_id ?? i}`} className="flex items-center gap-1.5 text-xs">
                  <StatusDot variant={r.passed ? "success" : "error"} size={6} />
                  <span className="text-[var(--foreground)]">{String(r.rule_name)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Rejection reason */}
        {order.state === "rejected" && order.rejection_reason && (
          <div className="rounded-md border border-[var(--destructive)]/20 bg-[var(--destructive-muted)] p-2 text-xs text-[var(--destructive)]">
            <p className="font-medium">Rejection Reason</p>
            <p className="mt-0.5">{order.rejection_reason}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 border-t border-[var(--border)] pt-3">
          <button
            type="button"
            onClick={() => onClone(order)}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-[var(--border)] py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
          >
            <Copy className="h-3 w-3" />
            Clone
          </button>
          {order.state === "filled" && (
            <Link
              href={`/${fundSlug}/orders/${order.id}/tca`}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-[var(--border)] py-1.5 text-xs font-medium text-[var(--primary)] transition-colors hover:bg-[var(--primary-muted)]"
            >
              <FileText className="h-3 w-3" />
              TCA
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-[var(--muted-foreground)]">{label}</p>
      <p className="font-mono text-xs font-medium">{value}</p>
    </div>
  );
}

function TimelineRow({ label, time }: { label: string; time: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <span className="font-mono text-[var(--foreground)]">{new Date(time).toLocaleString()}</span>
    </div>
  );
}
