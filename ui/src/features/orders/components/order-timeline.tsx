"use client";

import type { FillDetail, OrderSummary } from "../types";

// ─── State → dot color mapping ──────────────────────────────

const STATE_DOT_COLORS: Record<string, string> = {
  draft: "bg-[var(--muted-foreground)]",
  pending_compliance: "bg-[var(--warning)]",
  approved: "bg-[var(--primary)]",
  rejected: "bg-[var(--destructive)]",
  sent: "bg-[var(--primary)]",
  working: "bg-[var(--info,var(--primary))]",
  partially_filled: "bg-[var(--accent-purple)]",
  filled: "bg-[var(--success)]",
  cancelled: "bg-[var(--muted-foreground)]",
};

const STATE_LINE_COLORS: Record<string, string> = {
  rejected: "bg-[var(--destructive)]/30",
  cancelled: "bg-[var(--muted-foreground)]/30",
};

const STATE_LABELS: Record<string, string> = {
  draft: "Created",
  pending_compliance: "Pending Compliance",
  approved: "Approved",
  rejected: "Rejected",
  sent: "Sent",
  working: "Working",
  partially_filled: "Partially Filled",
  filled: "Filled",
  cancelled: "Cancelled",
};

// ─── Canonical state ordering for lifecycle reconstruction ───

const STATE_ORDER: string[] = [
  "draft",
  "pending_compliance",
  "approved",
  "sent",
  "working",
  "partially_filled",
  "filled",
];

/** Terminal states that end the timeline. */
const TERMINAL_STATES = new Set(["filled", "rejected", "cancelled"]);

// ─── Timeline entry ─────────────────────────────────────────

interface TimelineEntry {
  state: string;
  label: string;
  timestamp: string | null;
  detail: string | null;
  isCurrent: boolean;
}

/**
 * Reconstruct the order lifecycle as a timeline from the order summary and its
 * fills. Since the API doesn't expose an explicit state-transitions audit log,
 * we derive the sequence from the canonical state ordering, using the order's
 * `created_at` and fill timestamps to anchor events.
 */
function buildTimeline(order: OrderSummary, fills: FillDetail[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [];
  const currentIdx = STATE_ORDER.indexOf(order.state);
  const sortedFills = [...fills].sort(
    (a, b) => new Date(a.filled_at).getTime() - new Date(b.filled_at).getTime(),
  );

  // For terminal states that branch off the main flow (rejected, cancelled),
  // figure out which normal states were traversed first.
  const isRejected = order.state === "rejected";
  const isCancelled = order.state === "cancelled";

  // Walk the canonical states up to the current one (or the branch point).
  let walkUntil: number;
  if (isRejected) {
    // Rejected happens after pending_compliance (index 1)
    walkUntil = 1;
  } else if (isCancelled) {
    // Cancelled could happen at various points — infer from fills
    if (sortedFills.length > 0) {
      walkUntil = STATE_ORDER.indexOf("partially_filled");
    } else if (currentIdx >= 0) {
      walkUntil = currentIdx;
    } else {
      // Best guess: approved
      walkUntil = STATE_ORDER.indexOf("approved");
    }
  } else {
    walkUntil = currentIdx;
  }

  for (let i = 0; i <= Math.min(walkUntil, STATE_ORDER.length - 1); i++) {
    const state = STATE_ORDER[i];
    let timestamp: string | null = null;
    let detail: string | null = null;

    if (state === "draft") {
      timestamp = order.created_at;
    } else if (state === "partially_filled" && sortedFills.length > 0) {
      const f = sortedFills[0];
      timestamp = f.filled_at;
      detail = `${fmtQty(f.quantity)} @ $${fmtPrice(f.price)}`;
    } else if (state === "filled" && sortedFills.length > 0) {
      const f = sortedFills[sortedFills.length - 1];
      timestamp = f.filled_at;
      const totalQty = parseFloat(order.filled_quantity);
      const avgPx = order.avg_fill_price ? fmtPrice(order.avg_fill_price) : fmtPrice(f.price);
      detail = `${fmtQty(String(totalQty))} @ $${avgPx}`;
    }

    entries.push({
      state,
      label: STATE_LABELS[state] ?? state,
      timestamp,
      detail,
      isCurrent: !isRejected && !isCancelled && state === order.state,
    });
  }

  // Append terminal branch states
  if (isRejected) {
    entries.push({
      state: "rejected",
      label: STATE_LABELS.rejected,
      timestamp: order.updated_at,
      detail: order.rejection_reason,
      isCurrent: true,
    });
  } else if (isCancelled) {
    entries.push({
      state: "cancelled",
      label: STATE_LABELS.cancelled,
      timestamp: order.updated_at,
      detail: null,
      isCurrent: true,
    });
  }

  // Add intermediate fills (between first and last) as sub-entries on partially_filled
  // We skip this for simplicity — the fills table in the detail panel already shows them.

  return entries;
}

// ─── Formatters ─────────────────────────────────────────────

function fmtQty(q: string): string {
  return parseFloat(q).toLocaleString();
}

function fmtPrice(p: string): string {
  return parseFloat(p).toFixed(2);
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString([], { year: "numeric", month: "2-digit", day: "2-digit" });
}

// ─── Component ──────────────────────────────────────────────

interface OrderTimelineProps {
  order: OrderSummary;
  fills?: FillDetail[];
}

export function OrderTimeline({ order, fills = [] }: OrderTimelineProps) {
  const entries = buildTimeline(order, fills);

  if (entries.length === 0) return null;

  // Show the full date on the first entry, then just time for same-day entries
  const firstDate = entries[0].timestamp ? fmtDate(entries[0].timestamp) : null;

  return (
    <div className="relative">
      {entries.map((entry, i) => {
        const isLast = i === entries.length - 1;
        const dotColor = STATE_DOT_COLORS[entry.state] ?? "bg-[var(--muted-foreground)]";
        const lineColor = STATE_LINE_COLORS[entry.state] ?? "bg-[var(--border)]";
        const showDate =
          entry.timestamp && fmtDate(entry.timestamp) !== firstDate && i > 0;

        return (
          <div key={entry.state} className="relative flex gap-2.5 pb-2 last:pb-0">
            {/* Vertical line + dot */}
            <div className="flex flex-col items-center">
              <span
                className={`z-10 mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${dotColor} ${entry.isCurrent ? "ring-2 ring-[var(--ring)]" : ""}`}
              />
              {!isLast && (
                <span className={`w-px flex-1 ${lineColor}`} />
              )}
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
                  {showDate && (
                    <span className="mr-1">{fmtDate(entry.timestamp)}</span>
                  )}
                  {i === 0 && firstDate && (
                    <span className="mr-1">{firstDate}</span>
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
