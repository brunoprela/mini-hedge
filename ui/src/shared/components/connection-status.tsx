"use client";

import { useConnectionStatus } from "./realtime-provider";

const STATUS_CONFIG = {
  connected: { color: "bg-green-500", label: "Live" },
  connecting: { color: "bg-yellow-500 animate-pulse", label: "Connecting" },
  disconnected: { color: "bg-red-500", label: "Disconnected" },
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
