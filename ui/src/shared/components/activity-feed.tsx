"use client";

import { useState } from "react";
import { formatTimestamp } from "@/shared/lib/formatters";
import type { RealtimeEvent } from "./realtime-provider";
import { useRealtimeEvents } from "./realtime-provider";

interface ActivityItem {
  id: string;
  type: string;
  message: string;
  timestamp: string;
}

const MAX_ITEMS = 50;

function formatEvent(event: RealtimeEvent): string {
  const d = event.data;
  switch (event.event_type) {
    case "trade.buy":
      return `BUY ${d.quantity} ${d.instrument_id} @ ${d.price}`;
    case "trade.sell":
      return `SELL ${d.quantity} ${d.instrument_id} @ ${d.price}`;
    case "position.changed":
      return `${d.instrument_id} position updated — qty ${d.quantity}`;
    case "pnl.realized":
      return `${d.instrument_id} realized P&L: ${d.realized_pnl}`;
    case "pnl.mark_to_market":
      return `${d.instrument_id} MTM @ ${d.market_price}`;
    default:
      return event.event_type;
  }
}

/** Event types shown in the activity feed (not price ticks). */
const ACTIVITY_TYPES = new Set([
  "trade.buy",
  "trade.sell",
  "position.changed",
  "pnl.realized",
  "pnl.mark_to_market",
]);

export function ActivityFeed() {
  const [items, setItems] = useState<ActivityItem[]>([]);

  useRealtimeEvents((event) => {
    if (!ACTIVITY_TYPES.has(event.event_type)) return;

    const item: ActivityItem = {
      id: event.event_id ?? crypto.randomUUID(),
      type: event.event_type,
      message: formatEvent(event),
      timestamp: event.timestamp,
    };
    setItems((prev) => [item, ...prev].slice(0, MAX_ITEMS));
  });

  return (
    <div className="rounded-lg border border-[var(--border)]">
      <div className="border-b border-[var(--border)] px-4 py-2">
        <h3 className="text-sm font-medium">Live Activity</h3>
      </div>
      <div className="max-h-80 overflow-y-auto">
        {items.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
            Waiting for events...
          </p>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {items.map((item) => (
              <li key={item.id} className="flex items-start gap-3 px-4 py-2">
                <EventDot type={item.type} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{item.message}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {formatTimestamp(item.timestamp)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function EventDot({ type }: { type: string }) {
  const color =
    type === "trade.buy"
      ? "bg-green-500"
      : type === "trade.sell"
        ? "bg-red-500"
        : type.startsWith("pnl")
          ? "bg-blue-500"
          : "bg-gray-400";

  return <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${color}`} />;
}
