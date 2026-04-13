"use client";

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { SectionPanel } from "@/shared/components/section-panel";
import { activityLogQueryOptions } from "../api";
import type { AuditAction, AuditLogEntry } from "../types";

/* ------------------------------------------------------------------ */
/*  Action type metadata                                               */
/* ------------------------------------------------------------------ */

const ACTION_META: Record<
  AuditAction,
  { label: string; icon: string; dot: string }
> = {
  login:             { label: "Login",             icon: "\u279C", dot: "bg-[var(--primary)]" },
  order_placed:      { label: "Order Placed",      icon: "\u25B6", dot: "bg-[var(--success)]" },
  order_cancelled:   { label: "Order Cancelled",   icon: "\u2715", dot: "bg-[var(--destructive)]" },
  settings_changed:  { label: "Settings Changed",  icon: "\u2699", dot: "bg-[var(--warning)]" },
  api_key_created:   { label: "API Key Created",   icon: "+",      dot: "bg-[var(--success)]" },
  api_key_revoked:   { label: "API Key Revoked",   icon: "\u2212", dot: "bg-[var(--destructive)]" },
  export_csv:        { label: "CSV Export",         icon: "\u21E9", dot: "bg-[var(--primary)]" },
  password_changed:  { label: "Password Changed",  icon: "\u2022", dot: "bg-[var(--warning)]" },
  mfa_enabled:       { label: "MFA Enabled",       icon: "\u2713", dot: "bg-[var(--success)]" },
  mfa_disabled:      { label: "MFA Disabled",      icon: "!",      dot: "bg-[var(--destructive)]" },
};

const FILTER_OPTIONS: { label: string; value: AuditAction | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Login", value: "login" },
  { label: "Orders", value: "order_placed" },
  { label: "Cancelled", value: "order_cancelled" },
  { label: "Settings", value: "settings_changed" },
  { label: "API Keys", value: "api_key_created" },
  { label: "Export", value: "export_csv" },
];

const PAGE_SIZE = 20;

/* ------------------------------------------------------------------ */
/*  Formatters                                                         */
/* ------------------------------------------------------------------ */

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
    month: "short",
    day: "numeric",
  });
}

function shortDevice(ua?: string): string | null {
  if (!ua) return null;
  // Extract a rough browser/OS hint from the user-agent string
  if (ua.includes("Chrome")) return "Chrome";
  if (ua.includes("Firefox")) return "Firefox";
  if (ua.includes("Safari")) return "Safari";
  if (ua.includes("Edge")) return "Edge";
  return ua.length > 30 ? ua.slice(0, 30) + "\u2026" : ua;
}

/* ------------------------------------------------------------------ */
/*  Timeline entry row                                                 */
/* ------------------------------------------------------------------ */

function TimelineRow({
  entry,
  isLast,
  showDate,
}: {
  entry: AuditLogEntry;
  isLast: boolean;
  showDate: boolean;
}) {
  const meta = ACTION_META[entry.action as AuditAction] ?? {
    label: entry.action.replace(/_/g, " "),
    icon: "\u2022",
    dot: "bg-[var(--muted-foreground)]",
  };
  const device = shortDevice(entry.user_agent);

  return (
    <div className="relative flex gap-2.5 pb-1.5 last:pb-0">
      {/* Vertical line + dot */}
      <div className="flex flex-col items-center">
        <span
          className={`z-10 mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${meta.dot}`}
        />
        {!isLast && <span className="w-px flex-1 bg-[var(--border)]" />}
      </div>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5 pb-1">
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-1.5">
            <span className="text-[11px] text-[var(--muted-foreground)]">{meta.icon}</span>
            <span className="text-xs font-medium text-[var(--foreground)]">
              {meta.label}
            </span>
          </div>
          <span className="shrink-0 font-mono text-[11px] text-[var(--muted-foreground)]">
            {showDate && <span className="mr-1">{fmtDate(entry.timestamp)}</span>}
            {fmtTime(entry.timestamp)}
          </span>
        </div>

        <p className="text-[11px] leading-snug text-[var(--muted-foreground)]">
          {entry.description}
        </p>

        {(entry.ip_address || device) && (
          <p className="text-[10px] text-[var(--muted-foreground)]/70">
            {entry.ip_address && <span>{entry.ip_address}</span>}
            {entry.ip_address && device && <span className="mx-1">&middot;</span>}
            {device && <span>{device}</span>}
          </p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export function ActivityLog() {
  const { fundSlug } = useFundContext();
  const [filter, setFilter] = useState<AuditAction | "all">("all");
  const [offset, setOffset] = useState(0);

  const resetAndFilter = useCallback((value: AuditAction | "all") => {
    setFilter(value);
    setOffset(0);
  }, []);

  const { data, isLoading, isError } = useQuery(
    activityLogQueryOptions(fundSlug, {
      limit: PAGE_SIZE,
      offset,
      actionType: filter === "all" ? undefined : filter,
    }),
  );

  const entries = data?.entries ?? [];
  const hasMore = data?.has_more ?? false;

  // Determine date boundaries to show date headers
  let lastDateStr = "";

  return (
    <SectionPanel title="Recent Activity">
      {/* Filter chips */}
      <div className="flex flex-wrap gap-1.5 border-b border-[var(--border)] px-3 py-2">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => resetAndFilter(opt.value)}
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
              filter === opt.value
                ? "bg-[var(--primary)] text-white"
                : "bg-[var(--background)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Timeline */}
      <div className="px-3 py-3">
        {isLoading && entries.length === 0 && (
          <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
            Loading activity...
          </p>
        )}

        {isError && (
          <p className="py-6 text-center text-xs text-[var(--destructive)]">
            Failed to load activity log.
          </p>
        )}

        {!isLoading && !isError && entries.length === 0 && (
          <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
            No activity recorded yet.
          </p>
        )}

        {entries.length > 0 && (
          <div className="relative">
            {entries.map((entry, i) => {
              const dateStr = fmtDate(entry.timestamp);
              const showDate = dateStr !== lastDateStr;
              lastDateStr = dateStr;

              return (
                <TimelineRow
                  key={entry.id}
                  entry={entry}
                  isLast={i === entries.length - 1}
                  showDate={showDate}
                />
              );
            })}
          </div>
        )}

        {/* Load more */}
        {hasMore && (
          <div className="mt-2 flex justify-center border-t border-[var(--border)] pt-2">
            <button
              type="button"
              onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
              disabled={isLoading}
              className="rounded px-3 py-1 text-[11px] font-medium text-[var(--primary)] transition-colors hover:bg-[var(--primary-muted)] disabled:opacity-50"
            >
              {isLoading ? "Loading..." : "Load more"}
            </button>
          </div>
        )}
      </div>
    </SectionPanel>
  );
}
