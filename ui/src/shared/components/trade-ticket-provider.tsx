"use client";

import type { ReactNode } from "react";
import {
  useTradeTicketStore,
  type TradeTicketDefaults,
} from "@/shared/stores/trade-ticket-store";

export type { TradeTicketDefaults };

/**
 * Thin wrapper kept for layout compatibility — no longer holds state.
 * All state now lives in the Zustand store (`useTradeTicketStore`).
 */
export function TradeTicketProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

/**
 * Drop-in replacement hook.  Consumers get the same
 * `{ isOpen, defaults, openTradeTicket, closeTradeTicket }` shape.
 */
export function useTradeTicket() {
  const isOpen = useTradeTicketStore((s) => s.isOpen);
  const defaults = useTradeTicketStore((s) => s.defaults);
  const openTradeTicket = useTradeTicketStore((s) => s.openTradeTicket);
  const closeTradeTicket = useTradeTicketStore((s) => s.closeTradeTicket);

  return { isOpen, defaults, openTradeTicket, closeTradeTicket };
}
