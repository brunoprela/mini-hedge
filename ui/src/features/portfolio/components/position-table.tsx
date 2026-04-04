"use client";

import Link from "next/link";
import { useState } from "react";
import { Can } from "@/shared/components/can";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import {
  formatPnL,
  formatPrice,
  formatQuantity,
  formatTimestamp,
  pnlColorClass,
} from "@/shared/lib/formatters";
import { Permission } from "@/shared/lib/permissions";
import { usePositions } from "../hooks/use-positions";
import { LotDrawer } from "./lot-drawer";
import { TradeTicket } from "./trade-ticket";

export function PositionTable({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: positions, isLoading } = usePositions(portfolioId);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [showTradeTicket, setShowTradeTicket] = useState(false);

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading positions...</p>;
  }

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm text-[var(--muted-foreground)]">
          {positions?.length ?? 0} position{positions?.length !== 1 ? "s" : ""}
        </p>
        <Can permission={Permission.TRADES_EXECUTE}>
          <button
            type="button"
            onClick={() => setShowTradeTicket(true)}
            className="rounded-md bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90"
          >
            New Trade
          </button>
        </Can>
      </div>

      {!positions || positions.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          No positions in this portfolio. Execute a trade to get started.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
                <th className="px-4 py-2 text-left font-medium">Instrument</th>
                <th className="px-4 py-2 text-right font-medium">Qty</th>
                <th className="px-4 py-2 text-right font-medium">Avg Cost</th>
                <th className="px-4 py-2 text-right font-medium">Mkt Price</th>
                <th className="px-4 py-2 text-right font-medium">Mkt Value</th>
                <th className="px-4 py-2 text-right font-medium">Unrealized P&L</th>
                <th className="px-4 py-2 text-right font-medium">Updated</th>
                <th className="px-4 py-2 text-right font-medium">Orders</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <>
                  <tr
                    key={pos.instrument_id}
                    onClick={() =>
                      setExpandedRow(expandedRow === pos.instrument_id ? null : pos.instrument_id)
                    }
                    className="cursor-pointer border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-4 py-2 font-mono font-medium">
                      {pos.instrument_id}
                      <span className="ml-1 text-xs text-[var(--muted-foreground)]">
                        {expandedRow === pos.instrument_id ? "▼" : "▶"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">{formatQuantity(pos.quantity)}</td>
                    <td className="px-4 py-2 text-right">{formatPrice(pos.avg_cost)}</td>
                    <td className="px-4 py-2 text-right">{formatPrice(pos.market_price)}</td>
                    <td className="px-4 py-2 text-right">{formatPnL(pos.market_value)}</td>
                    <td
                      className={`px-4 py-2 text-right font-medium ${pnlColorClass(pos.unrealized_pnl)}`}
                    >
                      {formatPnL(pos.unrealized_pnl)}
                    </td>
                    <td className="px-4 py-2 text-right text-[var(--muted-foreground)]">
                      {formatTimestamp(pos.last_updated)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Link
                        href={`/${fundSlug}/portfolio/${portfolioId}#orders`}
                        className="text-[var(--foreground)] underline-offset-2 hover:underline"
                      >
                        Orders &rarr;
                      </Link>
                    </td>
                  </tr>
                  {expandedRow === pos.instrument_id && (
                    <LotDrawer portfolioId={portfolioId} instrumentId={pos.instrument_id} />
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showTradeTicket && (
        <TradeTicket portfolioId={portfolioId} onClose={() => setShowTradeTicket(false)} />
      )}
    </>
  );
}
