"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatusDot } from "@/shared/components/charts";
import { useConnectionStatus, useRealtimeEvents } from "@/shared/components/realtime-provider";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { eodHistoryQueryOptions } from "@/features/eod/api";

// ─── Connection Health (left) ──────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  connected: "Connected",
  connecting: "Connecting\u2026",
  disconnected: "Disconnected",
};

const STATUS_VARIANT: Record<string, "success" | "warning" | "error"> = {
  connected: "success",
  connecting: "warning",
  disconnected: "error",
};

function ConnectionHealth() {
  const status = useConnectionStatus();
  return (
    <span className="flex items-center gap-1.5">
      <StatusDot variant={STATUS_VARIANT[status]} size={6} />
      <span>{STATUS_LABEL[status]}</span>
    </span>
  );
}

// ─── Last Tick (center) ────────────────────────────────────

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function LastTick() {
  const [lastTick, setLastTick] = useState<string | null>(null);

  const onEvent = useCallback((e: { event_type: string; timestamp: string }) => {
    if (e.event_type === "price.updated") {
      setLastTick(e.timestamp);
    }
  }, []);

  useRealtimeEvents(onEvent);

  if (!lastTick) {
    return <span>Waiting for market data\u2026</span>;
  }
  return <span>Last tick: {formatTime(lastTick)}</span>;
}

// ─── EOD Status (right) ───────────────────────────────────

function EODStatus() {
  const { fundSlug } = useFundContext();
  const { data: history } = useQuery(eodHistoryQueryOptions(fundSlug));
  const latestRunRef = useRef<{ date: string; ok: boolean } | null>(null);

  // Track in-flight EOD via SSE
  const [running, setRunning] = useState(false);

  useRealtimeEvents(
    useCallback((e: { event_type: string }) => {
      if (e.event_type === "eod.run.started") setRunning(true);
      if (e.event_type === "eod.run.completed") setRunning(false);
    }, []),
  );

  useEffect(() => {
    if (history && history.length > 0) {
      const latest = history[0];
      latestRunRef.current = { date: latest.business_date, ok: latest.is_successful };
      // If latest run has no completed_at, it's still running
      if (!latest.completed_at) setRunning(true);
    }
  }, [history]);

  if (running) {
    return (
      <span className="flex items-center gap-1.5">
        <StatusDot variant="warning" size={6} />
        EOD: Running\u2026
      </span>
    );
  }

  if (latestRunRef.current) {
    const { date, ok } = latestRunRef.current;
    return (
      <span className="flex items-center gap-1.5">
        <StatusDot variant={ok ? "success" : "error"} size={6} />
        EOD: {ok ? "Completed" : "Failed"} {date}
      </span>
    );
  }

  return <span>EOD: No runs</span>;
}

// ─── Status Bar ───────────────────────────────────────────

export function StatusBar() {
  return (
    <div className="flex h-7 shrink-0 items-center justify-between border-t border-[var(--border)] bg-[var(--card)] px-3 text-xs text-[var(--muted-foreground)]">
      <ConnectionHealth />
      <LastTick />
      <EODStatus />
    </div>
  );
}
