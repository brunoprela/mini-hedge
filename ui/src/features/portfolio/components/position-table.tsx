"use client";

import {
  formatPrice,
  formatQuantity,
  formatPnL,
  pnlColorClass,
  formatTimestamp,
} from "@/shared/lib/formatters";
import { usePositions } from "../hooks/use-positions";

export function PositionTable({ portfolioId }: { portfolioId: string }) {
  const { data: positions, isLoading } = usePositions(portfolioId);

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading positions...</p>;
  }

  if (!positions || positions.length === 0) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">
        No positions in this portfolio. Execute a trade to get started.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
            <th className="px-4 py-2 text-left font-medium">Instrument</th>
            <th className="px-4 py-2 text-right font-medium">Qty</th>
            <th className="px-4 py-2 text-right font-medium">Avg Cost</th>
            <th className="px-4 py-2 text-right font-medium">Mkt Price</th>
            <th className="px-4 py-2 text-right font-medium">Mkt Value</th>
            <th className="px-4 py-2 text-right font-medium">Unrealized P&L</th>
            <th className="px-4 py-2 text-right font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => (
            <tr
              key={pos.instrument_id}
              className="border-b border-[var(--border)] last:border-0"
            >
              <td className="px-4 py-2 font-mono font-medium">
                {pos.instrument_id}
              </td>
              <td className="px-4 py-2 text-right">
                {formatQuantity(pos.quantity)}
              </td>
              <td className="px-4 py-2 text-right">
                {formatPrice(pos.avg_cost)}
              </td>
              <td className="px-4 py-2 text-right">
                {formatPrice(pos.market_price)}
              </td>
              <td className="px-4 py-2 text-right">
                {formatPnL(pos.market_value)}
              </td>
              <td className={`px-4 py-2 text-right font-medium ${pnlColorClass(pos.unrealized_pnl)}`}>
                {formatPnL(pos.unrealized_pnl)}
              </td>
              <td className="px-4 py-2 text-right text-[var(--muted-foreground)]">
                {formatTimestamp(pos.last_updated)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
