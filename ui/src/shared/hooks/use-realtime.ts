"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

type ConnectionStatus = "connecting" | "connected" | "disconnected";

const RECONNECT_DELAY = 5_000;

/**
 * Connects to the SSE stream via the BFF proxy and invalidates
 * React Query caches when real-time events arrive.
 *
 * Mount once at the fund layout level — all child components
 * benefit from cache invalidation automatically.
 */
export function useRealtime(fundSlug: string): {
  status: ConnectionStatus;
} {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const eventSourceRef = useRef<EventSource>(null);

  const invalidatePrices = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["prices"] });
  }, [queryClient]);

  const invalidatePositions = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["positions"] });
  }, [queryClient]);

  useEffect(() => {
    if (!fundSlug) return;

    function connect() {
      const es = new EventSource(`/api/stream?fundSlug=${fundSlug}`);
      eventSourceRef.current = es;
      setStatus("connecting");

      es.onopen = () => {
        setStatus("connected");
      };

      // Price events
      es.addEventListener("price.updated", invalidatePrices);

      // Position / P&L events
      es.addEventListener("position.changed", invalidatePositions);
      es.addEventListener("pnl.realized", invalidatePositions);
      es.addEventListener("pnl.mark_to_market", invalidatePositions);
      es.addEventListener("trade.buy", invalidatePositions);
      es.addEventListener("trade.sell", invalidatePositions);

      es.onerror = () => {
        setStatus("disconnected");
        es.close();
        eventSourceRef.current = null;

        // Auto-reconnect
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      };
    }

    connect();

    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setStatus("disconnected");
    };
  }, [fundSlug, invalidatePrices, invalidatePositions]);

  return { status };
}
