"use client";

import { useConnectionStatus } from "./realtime-provider";

const STATUS_CONFIG = {
  connected: { color: "bg-[var(--success)]", label: "Live" },
  connecting: { color: "bg-[var(--warning)] animate-pulse", label: "Connecting" },
  disconnected: { color: "bg-[var(--destructive)]", label: "Disconnected" },
} as const;

export function ConnectionStatus() {
  const status = useConnectionStatus();
  const config = STATUS_CONFIG[status];

  return (
    <div className="flex items-center gap-1.5" title={`Stream: ${config.label}`}>
      <span className={`inline-block h-2 w-2 rounded-full ${config.color}`} />
      <span className="text-xs text-[var(--muted-foreground)]">{config.label}</span>
    </div>
  );
}
