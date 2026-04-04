"use client";

import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";

type ConnectionStatus = "connecting" | "connected" | "disconnected";

/** Parsed SSE event forwarded to subscribers. */
export interface RealtimeEvent {
  event_type: string;
  data: Record<string, string>;
  timestamp: string;
  event_id?: string;
  fund_slug?: string;
}

type EventCallback = (event: RealtimeEvent) => void;

interface RealtimeContextValue {
  status: ConnectionStatus;
  /** Subscribe to SSE events. Returns an unsubscribe function. */
  subscribe: (cb: EventCallback) => () => void;
}

const RealtimeContext = createContext<RealtimeContextValue>({
  status: "disconnected",
  subscribe: () => () => {},
});

export function useConnectionStatus(): ConnectionStatus {
  return useContext(RealtimeContext).status;
}

/** Subscribe to all SSE events from the single shared connection. */
export function useRealtimeEvents(cb: EventCallback): void {
  const { subscribe } = useContext(RealtimeContext);
  const cbRef = useRef(cb);
  cbRef.current = cb;

  useEffect(() => {
    const handler: EventCallback = (e) => cbRef.current(e);
    return subscribe(handler);
  }, [subscribe]);
}

const RECONNECT_DELAY = 5_000;

const SSE_EVENT_TYPES = [
  "price.updated",
  "trade.buy",
  "trade.sell",
  "position.changed",
  "pnl.realized",
  "pnl.mark_to_market",
  "order.created",
  "order.filled",
  "trade.approved",
  "trade.rejected",
  "compliance.violation",
  "exposure.updated",
  "risk.updated",
  "cash.settlement.created",
  "cash.settlement.settled",
];

/**
 * Single SSE connection for the active fund.
 * - Invalidates React Query caches on events
 * - Exposes connection status and event subscription to children
 */
export function RealtimeProvider({ children }: { children?: ReactNode }) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const subscribersRef = useRef<Set<EventCallback>>(new Set());
  const eventSourceRef = useRef<EventSource>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(null);

  const subscribe = useCallback((cb: EventCallback) => {
    subscribersRef.current.add(cb);
    return () => {
      subscribersRef.current.delete(cb);
    };
  }, []);

  // Throttle invalidations: batch by type and flush at most once per second
  const priceFlushTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const pendingInstruments = useRef<Set<string>>(new Set());
  const positionFlushTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const pendingPortfolios = useRef<Set<string>>(new Set());

  const flushPriceInvalidations = useCallback(() => {
    const instruments = pendingInstruments.current;
    if (instruments.size === 0) return;

    for (const instrumentId of instruments) {
      queryClient.invalidateQueries({
        queryKey: ["prices", "latest", fundSlug, instrumentId],
      });
    }
    // Invalidate history queries once per flush (not per-instrument)
    queryClient.invalidateQueries({ queryKey: ["prices", "history"] });
    instruments.clear();
  }, [queryClient, fundSlug]);

  const flushPositionInvalidations = useCallback(() => {
    const portfolios = pendingPortfolios.current;
    if (portfolios.size === 0) return;

    for (const portfolioId of portfolios) {
      queryClient.invalidateQueries({
        queryKey: ["positions", fundSlug, portfolioId],
      });
      queryClient.invalidateQueries({
        queryKey: ["portfolio-summary", fundSlug, portfolioId],
      });
    }
    portfolios.clear();
  }, [queryClient, fundSlug]);

  useEffect(() => {
    if (!fundSlug) return;

    function handleEvent(eventType: string, messageEvent: MessageEvent) {
      try {
        const parsed = JSON.parse(messageEvent.data);
        const realtimeEvent: RealtimeEvent = {
          event_type: eventType,
          data: parsed.data ?? {},
          timestamp: parsed.timestamp ?? new Date().toISOString(),
          event_id: parsed.event_id,
          fund_slug: parsed.fund_slug,
        };

        // Invalidate React Query caches — scoped to specific portfolio/instrument
        const portfolioId = realtimeEvent.data.portfolio_id;

        if (eventType === "price.updated") {
          const instrumentId = realtimeEvent.data.instrument_id;
          if (instrumentId) {
            pendingInstruments.current.add(instrumentId);
          }
          if (!priceFlushTimer.current) {
            priceFlushTimer.current = setTimeout(() => {
              priceFlushTimer.current = null;
              flushPriceInvalidations();
            }, 1_000);
          }
        } else if (
          eventType === "trade.buy" ||
          eventType === "trade.sell" ||
          eventType === "position.changed" ||
          eventType === "pnl.realized" ||
          eventType === "pnl.mark_to_market"
        ) {
          // Throttle position invalidations — MTM ticks on every price change
          if (portfolioId) {
            pendingPortfolios.current.add(portfolioId);
          }
          if (!positionFlushTimer.current) {
            positionFlushTimer.current = setTimeout(() => {
              positionFlushTimer.current = null;
              flushPositionInvalidations();
            }, 2_000);
          }
        } else if (
          eventType === "order.created" ||
          eventType === "order.filled" ||
          eventType === "trade.approved" ||
          eventType === "trade.rejected"
        ) {
          if (portfolioId) {
            queryClient.invalidateQueries({
              queryKey: ["orders", fundSlug, portfolioId],
            });
          }
        } else if (eventType === "compliance.violation") {
          if (portfolioId) {
            queryClient.invalidateQueries({
              queryKey: ["violations", fundSlug, portfolioId],
            });
          }
        } else if (eventType === "exposure.updated") {
          if (portfolioId) {
            queryClient.invalidateQueries({
              queryKey: ["exposure", fundSlug, portfolioId],
            });
          }
        } else if (eventType === "risk.updated") {
          if (portfolioId) {
            queryClient.invalidateQueries({
              queryKey: ["risk-snapshot", fundSlug, portfolioId],
            });
          }
        } else if (
          eventType === "cash.settlement.created" ||
          eventType === "cash.settlement.settled"
        ) {
          if (portfolioId) {
            queryClient.invalidateQueries({
              queryKey: ["cash-balances", fundSlug, portfolioId],
            });
            queryClient.invalidateQueries({
              queryKey: ["settlements", fundSlug, portfolioId],
            });
          }
        }

        // Notify all subscribers (activity feed, etc.)
        for (const cb of subscribersRef.current) {
          cb(realtimeEvent);
        }
      } catch {
        // ignore parse errors
      }
    }

    function connect() {
      const es = new EventSource(`/api/stream?fundSlug=${fundSlug}`);
      eventSourceRef.current = es;
      setStatus("connecting");

      es.onopen = () => setStatus("connected");

      for (const type of SSE_EVENT_TYPES) {
        es.addEventListener(type, (e) => handleEvent(type, e));
      }

      es.onerror = () => {
        setStatus("disconnected");
        es.close();
        eventSourceRef.current = null;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      };
    }

    connect();

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (priceFlushTimer.current) clearTimeout(priceFlushTimer.current);
      if (positionFlushTimer.current) clearTimeout(positionFlushTimer.current);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      pendingInstruments.current.clear();
      pendingPortfolios.current.clear();
      setStatus("disconnected");
    };
  }, [fundSlug, queryClient, flushPriceInvalidations, flushPositionInvalidations]);

  const value: RealtimeContextValue = { status, subscribe };

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}
