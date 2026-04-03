"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { formatPrice, formatQuantity, formatTimestamp } from "@/shared/lib/formatters";
import { lotsQueryOptions } from "../api";

interface LotDrawerProps {
  portfolioId: string;
  instrumentId: string;
}

export function LotDrawer({ portfolioId, instrumentId }: LotDrawerProps) {
  const { fundSlug } = useFundContext();
  const { data: lots, isLoading } = useQuery(lotsQueryOptions(fundSlug, portfolioId, instrumentId));

  if (isLoading) {
    return (
      <tr>
        <td colSpan={7} className="px-4 py-2 text-xs text-[var(--muted-foreground)]">
          Loading lots...
        </td>
      </tr>
    );
  }

  if (!lots || lots.length === 0) {
    return (
      <tr>
        <td colSpan={7} className="px-4 py-2 text-xs text-[var(--muted-foreground)]">
          No lots
        </td>
      </tr>
    );
  }

  return (
    <>
      {lots.map((lot) => (
        <tr key={lot.id} className="bg-[var(--muted)]/50">
          <td className="pl-8 pr-4 py-1.5 text-xs text-[var(--muted-foreground)]">Lot</td>
          <td className="px-4 py-1.5 text-right text-xs font-mono">
            {formatQuantity(lot.quantity)}{" "}
            <span className="text-[var(--muted-foreground)]">
              / {formatQuantity(lot.original_quantity)}
            </span>
          </td>
          <td className="px-4 py-1.5 text-right text-xs font-mono">{formatPrice(lot.price)}</td>
          <td colSpan={2} className="px-4 py-1.5 text-right text-xs text-[var(--muted-foreground)]">
            {formatTimestamp(lot.acquired_at)}
          </td>
          <td
            colSpan={2}
            className="px-4 py-1.5 text-right text-xs font-mono text-[var(--muted-foreground)]"
          >
            {lot.trade_id.slice(0, 8)}...
          </td>
        </tr>
      ))}
    </>
  );
}
