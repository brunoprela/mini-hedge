"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { instrumentsQueryOptions } from "@/features/instruments/api";
import { SectionPanel } from "@/shared/components/section-panel";
import { Sparkline } from "@/shared/components/sparkline";
import { SortableHeader, TableSearch } from "@/shared/components/table-controls";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useTableState } from "@/shared/hooks/use-table-state";
import { formatPrice, formatTimestamp } from "@/shared/lib/formatters";
import { latestPriceQueryOptions, priceHistoryQueryOptions } from "../api";

/** Round a date down to the nearest 5 minutes for a stable query key. */
function roundTo5Min(date: Date): string {
  const d = new Date(date);
  d.setMinutes(Math.floor(d.getMinutes() / 5) * 5, 0, 0);
  return d.toISOString();
}

export function PriceDashboard() {
  const { fundSlug } = useFundContext();
  const { data: instruments, isLoading } = useQuery(instrumentsQueryOptions(fundSlug));

  // Fetch latest prices for all instruments
  const priceResults = useQueries({
    queries: (instruments ?? [])
      .slice(0, 30)
      .map((inst) => latestPriceQueryOptions(fundSlug, inst.ticker)),
  });

  // Stable time window for sparklines
  const { start, end } = useMemo(() => {
    const now = new Date();
    return {
      start: roundTo5Min(new Date(now.getTime() - 60 * 60 * 1000)),
      end: roundTo5Min(now),
    };
  }, []);

  // Fetch sparkline history for all instruments
  const historyResults = useQueries({
    queries: (instruments ?? [])
      .slice(0, 30)
      .map((inst) => priceHistoryQueryOptions(fundSlug, inst.ticker, start, end)),
  });

  // Build rows with instrument + price data merged
  const rows = useMemo(() => {
    if (!instruments) return [];
    return instruments.slice(0, 30).map((inst, i) => {
      const price = priceResults[i]?.data;
      const history = historyResults[i]?.data;
      const sparkData = history?.map((p) => Number(p.mid)) ?? [];
      const bid = price ? Number(price.bid) : null;
      const ask = price ? Number(price.ask) : null;
      const mid = price ? Number(price.mid) : null;
      const spread = bid !== null && ask !== null ? ask - bid : null;
      const spreadBps = mid && spread !== null ? (spread / mid) * 10000 : null;

      return {
        ticker: inst.ticker,
        name: inst.name,
        sector: inst.sector ?? "",
        currency: inst.currency,
        bid: bid ?? 0,
        ask: ask ?? 0,
        mid: mid ?? 0,
        spread: spread ?? 0,
        spreadBps: spreadBps ?? 0,
        volume: price?.volume ? Number(price.volume) : 0,
        timestamp: price?.timestamp ?? "",
        sparkData,
      };
    });
  }, [instruments, priceResults, historyResults]);

  const table = useTableState({
    data: rows as unknown as Record<string, unknown>[],
    initialSort: { key: "ticker", direction: "asc" },
    pageSize: 30,
    searchKeys: ["ticker", "name", "sector"],
  });

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>;
  }

  return (
    <SectionPanel
      title="Watchlist"
      actions={
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium text-[var(--muted-foreground)]">
            {table.totalFiltered} instruments
          </span>
          <div className="w-48">
            <TableSearch
              value={table.search}
              onChange={table.setSearch}
              placeholder="Search instruments..."
            />
          </div>
        </div>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-[var(--muted-foreground)]">
              <SortableHeader
                label="Ticker"
                sortKey="ticker"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <th className="px-3 py-1.5 text-xs font-medium">Name</th>
              <SortableHeader
                label="Bid"
                sortKey="bid"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Mid"
                sortKey="mid"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Ask"
                sortKey="ask"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Spread (bps)"
                sortKey="spreadBps"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <th className="px-3 py-1.5 text-xs font-medium">1h</th>
              <th className="px-3 py-1.5 text-xs font-medium">Sector</th>
              <th className="px-3 py-1.5 text-xs font-medium text-right">Updated</th>
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => {
              const r = row as unknown as (typeof rows)[number];
              return (
                <tr
                  key={r.ticker}
                  className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-3 py-1.5 font-mono text-sm font-medium text-[var(--foreground)]">
                    {r.ticker}
                  </td>
                  <td className="max-w-[160px] truncate px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                    {r.name}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs">
                    {r.bid ? formatPrice(String(r.bid)) : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs font-medium">
                    {r.mid ? formatPrice(String(r.mid)) : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs">
                    {r.ask ? formatPrice(String(r.ask)) : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs">
                    {r.spreadBps > 0 ? (
                      <span
                        className={
                          r.spreadBps > 10
                            ? "text-[var(--warning)]"
                            : "text-[var(--muted-foreground)]"
                        }
                      >
                        {r.spreadBps.toFixed(1)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-1.5">
                    {r.sparkData.length >= 2 ? (
                      <Sparkline data={r.sparkData} width={80} height={20} />
                    ) : (
                      <span className="text-[10px] text-[var(--muted-foreground)]">—</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                    {r.sector || "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right text-xs text-[var(--muted-foreground)]">
                    {r.timestamp ? formatTimestamp(r.timestamp) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </SectionPanel>
  );
}
