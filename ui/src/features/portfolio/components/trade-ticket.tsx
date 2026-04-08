"use client";

import { TradeTicketInner } from "./trade-ticket-inner";

interface TradeTicketProps {
  portfolioId: string;
  onClose: () => void;
  defaults?: { instrument?: string; side?: string; quantity?: string };
}

/**
 * Modal wrapper around TradeTicketInner — legacy usage from portfolio detail page.
 * The preferred path is the persistent TradeTicketPanel in the layout.
 */
export function TradeTicket({ portfolioId, onClose, defaults }: TradeTicketProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="flex w-full max-w-lg flex-col rounded-md border border-[var(--border)] bg-[var(--background)] shadow-lg" style={{ maxHeight: "90vh" }}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold">New Order</h2>
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Order Details</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        <TradeTicketInner portfolioId={portfolioId} onClose={onClose} defaults={defaults} />
      </div>
    </div>
  );
}
