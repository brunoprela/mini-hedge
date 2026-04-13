"use client";

import { Check, Clock, X } from "lucide-react";
import Link from "next/link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import type { Violation } from "../types";
import { ViolationTimeline } from "./violation-timeline";

const SEVERITY_BADGE: Record<string, string> = {
  block: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
  warning: "bg-[var(--warning-muted)] text-[var(--warning)]",
  breach: "bg-[var(--accent-orange-muted)] text-[var(--accent-orange)]",
};

const STATUS_BADGE: Record<string, { className: string; label: string }> = {
  resolved: {
    className: "bg-[var(--success)]/10 text-[var(--success)]",
    label: "Resolved",
  },
  waived: {
    className: "bg-[var(--muted)] text-[var(--muted-foreground)]",
    label: "Waived",
  },
  active: {
    className: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
    label: "Active",
  },
};

function getStatus(v: Violation): "resolved" | "waived" | "active" {
  if (v.resolution_type === "waived") return "waived";
  if (v.resolved_at) return "resolved";
  return "active";
}

interface ViolationDetailPanelProps {
  violation: Violation;
  onClose: () => void;
  canWrite: boolean;
  onResolve: (id: string) => void;
  onWaive: (id: string) => void;
  isResolving: boolean;
}

export function ViolationDetailPanel({
  violation,
  onClose,
  canWrite,
  onResolve,
  onWaive,
  isResolving,
}: ViolationDetailPanelProps) {
  const { fundSlug } = useFundContext();
  const status = getStatus(violation);
  const statusInfo = STATUS_BADGE[status];
  const isActionable = !violation.resolved_at;

  return (
    <div className="w-[340px] shrink-0 overflow-y-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-semibold truncate">{violation.rule_name}</span>
          <span
            className={`inline-block shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_BADGE[violation.severity] ?? ""}`}
          >
            {violation.severity}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="space-y-3 p-3">
        {/* Status + breach type */}
        <div className="grid grid-cols-2 gap-2">
          <DetailField label="Status">
            <span
              className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusInfo.className}`}
            >
              {statusInfo.label}
            </span>
          </DetailField>
          <DetailField label="Breach Type">
            <span className="font-mono text-xs font-medium capitalize">
              {violation.breach_type}
            </span>
          </DetailField>
        </div>

        {/* Message */}
        <div>
          <p className="text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider">
            Message
          </p>
          <p className="mt-0.5 text-xs text-[var(--foreground)]">{violation.message}</p>
        </div>

        {/* Detected timestamp */}
        <DetailField label="Detected">
          <span className="font-mono text-xs">
            {new Date(violation.detected_at).toLocaleString()}
          </span>
        </DetailField>

        {/* Current / Limit values */}
        {(violation.current_value != null || violation.limit_value != null) && (
          <div className="grid grid-cols-2 gap-2">
            <DetailField label="Current Value">
              <span className="font-mono text-xs font-medium text-[var(--destructive)]">
                {violation.current_value ?? "—"}
              </span>
            </DetailField>
            <DetailField label="Limit">
              <span className="font-mono text-xs font-medium">
                {violation.limit_value ?? "—"}
              </span>
            </DetailField>
          </div>
        )}

        {/* Deadline */}
        {violation.deadline_at && (
          <DetailField label="Deadline">
            <span className="font-mono text-xs">
              {new Date(violation.deadline_at).toLocaleString()}
            </span>
          </DetailField>
        )}

        {/* Portfolio context */}
        <div>
          <p className="text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider">
            Portfolio
          </p>
          <Link
            href={`/${fundSlug}/portfolio/${violation.portfolio_id}#positions`}
            className="mt-0.5 inline-block font-mono text-xs text-[var(--foreground)] underline-offset-2 hover:underline"
          >
            {violation.portfolio_id}
          </Link>
        </div>

        {/* Resolution info */}
        {violation.resolved_at && (
          <div className="grid grid-cols-2 gap-2">
            <DetailField label="Resolved At">
              <span className="font-mono text-xs">
                {new Date(violation.resolved_at).toLocaleString()}
              </span>
            </DetailField>
            {violation.resolved_by && (
              <DetailField label="Resolved By">
                <span className="text-xs">{violation.resolved_by}</span>
              </DetailField>
            )}
          </div>
        )}

        {/* Timeline */}
        <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] p-2">
          <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            <Clock className="h-3 w-3" />
            Timeline
          </div>
          <ViolationTimeline violation={violation} />
        </div>

        {/* Actions */}
        {canWrite && isActionable && (
          <div className="flex gap-2 border-t border-[var(--border)] pt-3">
            <button
              type="button"
              onClick={() => onResolve(violation.id)}
              disabled={isResolving}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] py-1.5 text-xs font-medium text-[var(--primary-foreground)] transition-colors hover:opacity-90 disabled:opacity-50"
            >
              <Check className="h-3 w-3" />
              {isResolving ? "Resolving..." : "Resolve"}
            </button>
            <button
              type="button"
              onClick={() => onWaive(violation.id)}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border border-[var(--border)] py-1.5 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
            >
              Waive
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider">
        {label}
      </p>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}
