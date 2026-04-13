"use client";

import type { ReactNode } from "react";
import { useTradeTicket } from "./trade-ticket-provider";

interface InstrumentLinkProps {
  instrument: string;
  side?: "buy" | "sell";
  children?: ReactNode;
  className?: string;
}

/**
 * Renders an instrument name as a clickable element that opens the trade ticket
 * pre-filled with the instrument. Use throughout tables and lists to make
 * instrument names interactive.
 */
export function InstrumentLink({ instrument, side, children, className }: InstrumentLinkProps) {
  const { openTradeTicket } = useTradeTicket();

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        openTradeTicket({ instrument, side });
      }}
      className={
        className ??
        "cursor-pointer text-left font-mono font-medium text-[var(--foreground)] underline-offset-2 transition-colors hover:text-[var(--primary)] hover:underline"
      }
    >
      {children ?? instrument}
    </button>
  );
}
