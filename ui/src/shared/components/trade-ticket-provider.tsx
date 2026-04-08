"use client";

import { createContext, type ReactNode, useCallback, useContext, useState } from "react";

export interface TradeTicketDefaults {
  instrument?: string;
  side?: "buy" | "sell";
  quantity?: string;
  portfolioId?: string;
}

interface TradeTicketContextValue {
  isOpen: boolean;
  defaults: TradeTicketDefaults;
  openTradeTicket: (defaults?: TradeTicketDefaults) => void;
  closeTradeTicket: () => void;
}

const TradeTicketContext = createContext<TradeTicketContextValue | null>(null);

export function TradeTicketProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [defaults, setDefaults] = useState<TradeTicketDefaults>({});

  const openTradeTicket = useCallback((d?: TradeTicketDefaults) => {
    setDefaults(d ?? {});
    setIsOpen(true);
  }, []);

  const closeTradeTicket = useCallback(() => {
    setIsOpen(false);
  }, []);

  return (
    <TradeTicketContext.Provider value={{ isOpen, defaults, openTradeTicket, closeTradeTicket }}>
      {children}
    </TradeTicketContext.Provider>
  );
}

export function useTradeTicket() {
  const ctx = useContext(TradeTicketContext);
  if (!ctx) throw new Error("useTradeTicket must be used within TradeTicketProvider");
  return ctx;
}
