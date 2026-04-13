"use client";

import type { Violation } from "../types";

// ─── Severity → dot color ───────────────────────────────────

const SEVERITY_DOT: Record<string, string> = {
  block: "bg-[var(--destructive)]",
  warning: "bg-[var(--warning)]",
  breach: "bg-[var(--accent-orange)]",
};

const RESOLUTION_DOT: Record<string, string> = {
  manual: "bg-[var(--success)]",
  auto: "bg-[var(--success)]",
  waived: "bg-[var(--muted-foreground)]",
};

const RESOLUTION_LABEL: Record<string, string> = {
  manual: "Resolved manually",
  auto: "Auto-resolved",
  waived: "Waived",
};

// ─── Timeline entry ─────────────────────────────────────────

interface TimelineEntry {
  key: string;
  label: string;
  detail: string | null;
  timestamp: string | null;
  dotColor: string;
  isCurrent: boolean;
}

/**
 * Build a lifecycle timeline from a single violation's fields.
 * Events: detected -> (deadline approaching) -> resolved/waived, or still open.
 */
function buildTimeline(v: Violation): TimelineEntry[] {
  const entries: TimelineEntry[] = [];
  const sevDot = SEVERITY_DOT[v.severity] ?? "bg-[var(--muted-foreground)]";
  const isResolved = !!v.resolved_at;

  // 1. Detected
  entries.push({
    key: "detected",
    label: "Detected",
    detail: `${v.rule_name} — ${v.message}`,
    timestamp: v.detected_at,
    dotColor: sevDot,
    isCurrent: !isResolved && !v.deadline_at,
  });

  // 2. Breach details (current vs limit)
  if (v.current_value != null && v.limit_value != null) {
    entries.push({
      key: "breach-detail",
      label: "Limit breached",
      detail: `Current: ${v.current_value} / Limit: ${v.limit_value}`,
      timestamp: null,
      dotColor: sevDot,
      isCurrent: false,
    });
  }

  // 3. Deadline (if set and not yet resolved)
  if (v.deadline_at) {
    const isPast = new Date(v.deadline_at).getTime() < Date.now();
    entries.push({
      key: "deadline",
      label: isPast ? "Deadline passed" : "Deadline",
      detail: null,
      timestamp: v.deadline_at,
      dotColor: isPast && !isResolved ? "bg-[var(--destructive)]" : "bg-[var(--warning)]",
      isCurrent: !isResolved,
    });
  }

  // 4. Resolution
  if (isResolved && v.resolution_type) {
    entries.push({
      key: "resolved",
      label: RESOLUTION_LABEL[v.resolution_type] ?? "Resolved",
      detail: v.resolved_by ? `By ${v.resolved_by}` : null,
      timestamp: v.resolved_at!,
      dotColor: RESOLUTION_DOT[v.resolution_type] ?? "bg-[var(--success)]",
      isCurrent: true,
    });
  }

  return entries;
}

// ─── Formatters ─────────────────────────────────────────────

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

// ─── Component ──────────────────────────────────────────────

interface ViolationTimelineProps {
  violation: Violation;
}

export function ViolationTimeline({ violation }: ViolationTimelineProps) {
  const entries = buildTimeline(violation);

  if (entries.length === 0) return null;

  const firstDate = entries[0].timestamp ? fmtDate(entries[0].timestamp) : null;

  return (
    <div className="relative">
      {entries.map((entry, i) => {
        const isLast = i === entries.length - 1;
        const showDate = entry.timestamp && i > 0 && fmtDate(entry.timestamp) !== firstDate;

        return (
          <div key={entry.key} className="relative flex gap-2.5 pb-2 last:pb-0">
            {/* Vertical line + dot */}
            <div className="flex flex-col items-center">
              <span
                className={`z-10 mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${entry.dotColor} ${entry.isCurrent ? "ring-2 ring-[var(--ring)]" : ""}`}
              />
              {!isLast && <span className="w-px flex-1 bg-[var(--border)]" />}
            </div>

            {/* Content */}
            <div className="flex min-w-0 flex-1 items-baseline justify-between gap-2 pb-1">
              <div className="flex items-baseline gap-1.5">
                <span
                  className={`text-xs font-medium ${
                    entry.isCurrent
                      ? "text-[var(--foreground)]"
                      : "text-[var(--muted-foreground)]"
                  }`}
                >
                  {entry.label}
                </span>
                {entry.detail && (
                  <span className="text-[11px] text-[var(--muted-foreground)]">
                    — {entry.detail}
                  </span>
                )}
              </div>
              {entry.timestamp && (
                <span className="shrink-0 font-mono text-[11px] text-[var(--muted-foreground)]">
                  {(showDate || (i === 0 && firstDate)) && (
                    <span className="mr-1">
                      {showDate ? fmtDate(entry.timestamp) : firstDate}
                    </span>
                  )}
                  {fmtTime(entry.timestamp)}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
