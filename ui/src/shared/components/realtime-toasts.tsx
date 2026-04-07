"use client";

import { toast } from "sonner";
import { useRealtimeEvents } from "./realtime-provider";

/**
 * Invisible component that listens to SSE events and shows toast
 * notifications for important (low-frequency) events.
 */
export function RealtimeToasts() {
  useRealtimeEvents((event) => {
    const d = event.data;

    switch (event.event_type) {
      case "compliance.violation":
        toast.error(d.rule_name ? `Compliance violation detected: ${d.rule_name}` : "New violation");
        break;
      case "trade.rejected":
        toast.error(d.reason ? `Trade rejected: ${d.reason}` : "Trade was rejected");
        break;
      case "order.filled":
        toast.success(
          d.instrument_id
            ? `Order filled: ${d.instrument_id} ${d.side} ${d.quantity}`
            : "Order filled",
        );
        break;
      case "eod.run.completed":
        toast.info("EOD run completed");
        break;
    }
  });

  return null;
}
