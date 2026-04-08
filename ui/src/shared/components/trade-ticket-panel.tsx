"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { TradeTicketInner } from "@/features/portfolio/components/trade-ticket-inner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useTradeTicket } from "./trade-ticket-provider";

/**
 * Slide-out trade ticket panel — renders in the layout, accessible from any page.
 */
export function TradeTicketPanel() {
  const { fundSlug } = useFundContext();
  const { isOpen, defaults, closeTradeTicket } = useTradeTicket();
  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  const portfolioId = defaults.portfolioId || portfolios?.[0]?.id || "";

  if (!isOpen) return null;

  return (
    <div className="flex h-full w-[380px] shrink-0 flex-col border-l border-[var(--border)] bg-[var(--background)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
        <div>
          <h2 className="text-sm font-semibold">Trade Ticket</h2>
          <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Order Entry</p>
        </div>
        <button
          type="button"
          onClick={closeTradeTicket}
          className="flex h-6 w-6 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {portfolioId ? (
          <TradeTicketInner
            portfolioId={portfolioId}
            onClose={closeTradeTicket}
            defaults={{
              instrument: defaults.instrument,
              side: defaults.side,
              quantity: defaults.quantity,
            }}
            portfolios={portfolios ?? []}
            showPortfolioSelector
          />
        ) : (
          <p className="px-4 py-8 text-center text-xs text-[var(--muted-foreground)]">
            No portfolios available
          </p>
        )}
      </div>
    </div>
  );
}
