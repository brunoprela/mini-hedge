"use client";

import { TableSkeleton } from "@mini-hedge/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  List,
  Plus,
  Star,
  Trash2,
} from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { instrumentsQueryOptions } from "@/features/instruments/api";
import { LineChart } from "@/shared/components/charts";
import { InstrumentLink } from "@/shared/components/instrument-link";
import { SectionPanel } from "@/shared/components/section-panel";
import {
  SortableHeader,
  TablePagination,
  TableSearch,
} from "@/shared/components/table-controls";
import { useTradeTicket } from "@/shared/components/trade-ticket-provider";
import { useFlashOnChange } from "@/shared/hooks/use-flash-on-change";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useTableState } from "@/shared/hooks/use-table-state";
import { formatPrice, formatTimestamp } from "@/shared/lib/formatters";
import { useWatchlistStore } from "@/shared/stores/watchlist-store";
import { latestPriceQueryOptions, priceHistoryQueryOptions } from "../api";
import type { PriceSnapshot } from "../types";

/** Round a date down to the nearest 5 minutes for a stable query key. */
function roundTo5Min(date: Date): string {
  const d = new Date(date);
  d.setMinutes(Math.floor(d.getMinutes() / 5) * 5, 0, 0);
  return d.toISOString();
}

/** Format large numbers with K/M suffixes. */
function formatVolume(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toLocaleString();
}

/** Mini bar showing where the current price sits between the day low and high. */
function DailyRangeBar({
  low,
  high,
  current,
}: {
  low: number;
  high: number;
  current: number;
}) {
  const range = high - low;
  const pct = range > 0 ? ((current - low) / range) * 100 : 50;
  const clamped = Math.max(0, Math.min(100, pct));

  return (
    <div className="flex items-center gap-1.5">
      <span className="font-mono text-[10px] text-[var(--muted-foreground)]">
        {formatPrice(String(low))}
      </span>
      <div className="relative h-1.5 w-16 rounded-full bg-[var(--border)]">
        <div
          className="absolute top-0 left-0 h-full rounded-full bg-[var(--muted-foreground)] opacity-30"
          style={{ width: "100%" }}
        />
        <div
          className="absolute top-[-1px] h-2 w-0.5 rounded-full bg-[var(--foreground)]"
          style={{ left: `${clamped}%` }}
        />
      </div>
      <span className="font-mono text-[10px] text-[var(--muted-foreground)]">
        {formatPrice(String(high))}
      </span>
    </div>
  );
}

/** A single stat cell in the expanded detail grid. */
function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
        {label}
      </p>
      <p className="font-mono text-xs font-medium text-[var(--foreground)]">{value}</p>
    </div>
  );
}

/** Table cell that flashes green/red when its numeric value changes. */
function FlashCell({ value, formatted }: { value: number; formatted: string }) {
  const flash = useFlashOnChange(value);
  return (
    <td className={`px-2 py-1 text-right font-mono font-medium ${flash}`}>
      {formatted}
    </td>
  );
}

/** Expanded detail section: intraday chart + stats grid + trade button. */
function ExpandedRowDetail({
  row,
  history,
  hasStarColumn,
}: {
  row: WatchlistRow;
  history: PriceSnapshot[] | undefined;
  hasStarColumn: boolean;
}) {
  const { openTradeTicket } = useTradeTicket();

  // Build chart data from history
  const chartSeries = useMemo(() => {
    if (!history || history.length < 2) return [];
    return [
      {
        label: row.ticker,
        color: "var(--primary)",
        data: history.map((p) => ({
          x: new Date(p.timestamp).toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
          }),
          y: Number(p.mid),
        })),
      },
    ];
  }, [history, row.ticker]);

  // Compute open from first history point
  const openPrice =
    history && history.length > 0 ? formatPrice(String(history[0].mid)) : "\u2014";
  // Close is the latest price
  const closePrice = row.lastPrice ? formatPrice(String(row.lastPrice)) : "\u2014";

  const colSpan = hasStarColumn ? 14 : 13; // 12 data columns + 1 chevron + optional star

  return (
    <tr>
      <td colSpan={colSpan} className="p-0">
        <div className="border-t border-[var(--border)] bg-[var(--card)] px-4 py-3">
          <div className="flex gap-6">
            {/* Intraday chart */}
            <div className="min-w-0 flex-1">
              <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Intraday Price
              </p>
              {chartSeries.length > 0 ? (
                <LineChart
                  series={chartSeries}
                  height={140}
                  showXLabels
                  xLabelInterval={Math.max(
                    1,
                    Math.floor((chartSeries[0]?.data.length ?? 1) / 6),
                  )}
                  formatY={(v) => formatPrice(String(v))}
                />
              ) : (
                <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
                  Not enough data
                </p>
              )}
            </div>

            {/* Stats grid + trade button */}
            <div className="flex w-56 shrink-0 flex-col justify-between">
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                <StatCell label="Open" value={openPrice} />
                <StatCell label="Close" value={closePrice} />
                <StatCell
                  label="Day High"
                  value={row.dayHigh > 0 ? formatPrice(String(row.dayHigh)) : "\u2014"}
                />
                <StatCell
                  label="Day Low"
                  value={row.dayLow > 0 ? formatPrice(String(row.dayLow)) : "\u2014"}
                />
                <StatCell label="52w High" value={"\u2014"} />
                <StatCell label="52w Low" value={"\u2014"} />
                <StatCell label="Market Cap" value={"\u2014"} />
                <StatCell
                  label="Avg Volume"
                  value={row.volume > 0 ? formatVolume(row.volume) : "\u2014"}
                />
              </div>
              <button
                type="button"
                className="mt-3 w-full rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:opacity-90"
                onClick={() => openTradeTicket({ instrument: row.ticker })}
              >
                Trade {row.ticker}
              </button>
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
}

interface WatchlistRow {
  ticker: string;
  name: string;
  sector: string;
  currency: string;
  lastPrice: number;
  change: number;
  changePct: number;
  bid: number;
  ask: number;
  volume: number;
  vwap: number;
  dayHigh: number;
  dayLow: number;
  timestamp: string;
}

/** A single watchlist row that can expand to show intraday chart + stats. */
function ExpandableRow({
  row: r,
  isExpanded,
  changeColor,
  history,
  onToggle,
  isInWatchlist,
  onToggleStar,
}: {
  row: WatchlistRow;
  isExpanded: boolean;
  changeColor: string;
  history: PriceSnapshot[] | undefined;
  onToggle: (ticker: string) => void;
  isInWatchlist: boolean | null;
  onToggleStar: ((ticker: string) => void) | null;
}) {
  const Chevron = isExpanded ? ChevronDown : ChevronRight;

  return (
    <>
      <tr
        className="cursor-pointer hover:bg-[var(--table-row-hover)]"
        onClick={() => onToggle(r.ticker)}
      >
        {/* Expand chevron */}
        <td className="px-1 py-1 text-center">
          <Chevron className="inline-block h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        </td>

        {/* Watchlist star */}
        {onToggleStar !== null && (
          <td className="px-1 py-1 text-center">
            <button
              type="button"
              className="rounded p-0.5 transition-colors hover:text-[var(--primary)]"
              title={isInWatchlist ? "Remove from watchlist" : "Add to watchlist"}
              onClick={(e) => {
                e.stopPropagation();
                onToggleStar(r.ticker);
              }}
            >
              <Star
                className={`h-3.5 w-3.5 ${
                  isInWatchlist
                    ? "fill-[var(--primary)] text-[var(--primary)]"
                    : "text-[var(--muted-foreground)]"
                }`}
              />
            </button>
          </td>
        )}

        {/* Ticker */}
        <td className="px-2 py-1" onClick={(e) => e.stopPropagation()}>
          <InstrumentLink instrument={r.ticker} />
        </td>

        {/* Last Price */}
        <FlashCell
          value={r.lastPrice}
          formatted={r.lastPrice ? formatPrice(String(r.lastPrice)) : "\u2014"}
        />

        {/* Change */}
        <td className={`px-2 py-1 text-right font-mono ${changeColor}`}>
          {r.change !== 0
            ? `${r.change > 0 ? "+" : ""}${r.change.toFixed(2)}`
            : "\u2014"}
        </td>

        {/* Change % */}
        <td className={`px-2 py-1 text-right font-mono ${changeColor}`}>
          {r.changePct !== 0
            ? `${r.changePct > 0 ? "+" : ""}${r.changePct.toFixed(2)}%`
            : "\u2014"}
        </td>

        {/* Bid */}
        <td className="px-2 py-1 text-right font-mono">
          {r.bid ? formatPrice(String(r.bid)) : "\u2014"}
        </td>

        {/* Ask */}
        <td className="px-2 py-1 text-right font-mono">
          {r.ask ? formatPrice(String(r.ask)) : "\u2014"}
        </td>

        {/* Volume */}
        <td className="px-2 py-1 text-right font-mono">
          {r.volume > 0 ? formatVolume(r.volume) : "\u2014"}
        </td>

        {/* VWAP */}
        <td className="px-2 py-1 text-right font-mono">
          {r.vwap > 0 ? formatPrice(String(r.vwap)) : "\u2014"}
        </td>

        {/* Day High */}
        <td className="px-2 py-1 text-right font-mono">
          {r.dayHigh > 0 ? formatPrice(String(r.dayHigh)) : "\u2014"}
        </td>

        {/* Day Low */}
        <td className="px-2 py-1 text-right font-mono">
          {r.dayLow > 0 ? formatPrice(String(r.dayLow)) : "\u2014"}
        </td>

        {/* Daily Range */}
        <td className="px-2 py-1">
          {r.dayHigh > 0 && r.dayLow > 0 && r.lastPrice > 0 ? (
            <DailyRangeBar low={r.dayLow} high={r.dayHigh} current={r.lastPrice} />
          ) : (
            "\u2014"
          )}
        </td>

        {/* Updated */}
        <td className="px-2 py-1 text-right text-[var(--muted-foreground)]">
          {r.timestamp ? formatTimestamp(r.timestamp) : "\u2014"}
        </td>
      </tr>
      {isExpanded && <ExpandedRowDetail row={r} history={history} hasStarColumn={onToggleStar !== null} />}
    </>
  );
}

/** Dropdown for selecting / managing custom watchlists. */
function WatchlistSelector() {
  const {
    watchlists,
    activeWatchlistId,
    setActiveWatchlist,
    createWatchlist,
    deleteWatchlist,
    renameWatchlist,
  } = useWatchlistStore();

  const [open, setOpen] = useState(false);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameName, setRenameName] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeWatchlist = watchlists.find((w) => w.id === activeWatchlistId);

  const handleCreate = () => {
    const name = prompt("Watchlist name:");
    if (name?.trim()) {
      createWatchlist(name.trim());
    }
    setOpen(false);
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteWatchlist(id);
  };

  const handleRenameStart = (e: React.MouseEvent, w: { id: string; name: string }) => {
    e.stopPropagation();
    setRenameId(w.id);
    setRenameName(w.name);
  };

  const handleRenameSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (renameId && renameName.trim()) {
      renameWatchlist(renameId, renameName.trim());
    }
    setRenameId(null);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        className="flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-1 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--table-row-hover)]"
        onClick={() => setOpen((v) => !v)}
      >
        <List className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <span>{activeWatchlist ? activeWatchlist.name : "All Instruments"}</span>
        <ChevronDown className="h-3 w-3 text-[var(--muted-foreground)]" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[200px] rounded-md border border-[var(--border)] bg-[var(--card)] py-1 shadow-lg">
          {/* All Instruments option */}
          <button
            type="button"
            className={`flex w-full items-center px-3 py-1.5 text-left text-xs transition-colors hover:bg-[var(--table-row-hover)] ${
              activeWatchlistId === null
                ? "font-medium text-[var(--primary)]"
                : "text-[var(--foreground)]"
            }`}
            onClick={() => {
              setActiveWatchlist(null);
              setOpen(false);
            }}
          >
            All Instruments
          </button>

          {watchlists.length > 0 && (
            <div className="my-1 border-t border-[var(--border)]" />
          )}

          {/* User watchlists */}
          {watchlists.map((w) => (
            <div
              key={w.id}
              className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-xs transition-colors hover:bg-[var(--table-row-hover)] ${
                activeWatchlistId === w.id
                  ? "font-medium text-[var(--primary)]"
                  : "text-[var(--foreground)]"
              }`}
            >
              {renameId === w.id ? (
                <form
                  onSubmit={handleRenameSubmit}
                  className="flex-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    // eslint-disable-next-line jsx-a11y/no-autofocus
                    autoFocus
                    className="w-full rounded border border-[var(--border)] bg-[var(--background)] px-1.5 py-0.5 text-xs text-[var(--foreground)] outline-none"
                    value={renameName}
                    onChange={(e) => setRenameName(e.target.value)}
                    onBlur={handleRenameSubmit}
                  />
                </form>
              ) : (
                <button
                  type="button"
                  className="flex-1 text-left"
                  onClick={() => {
                    setActiveWatchlist(w.id);
                    setOpen(false);
                  }}
                >
                  {w.name}
                  <span className="ml-1 text-[10px] text-[var(--muted-foreground)]">
                    ({w.tickers.length})
                  </span>
                </button>
              )}

              <div className="flex items-center gap-0.5">
                <button
                  type="button"
                  className="rounded p-0.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  title="Rename"
                  onClick={(e) => handleRenameStart(e, w)}
                >
                  <span className="text-[10px]">✎</span>
                </button>
                <button
                  type="button"
                  className="rounded p-0.5 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
                  title="Delete"
                  onClick={(e) => handleDelete(e, w.id)}
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}

          <div className="my-1 border-t border-[var(--border)]" />

          {/* New Watchlist */}
          <button
            type="button"
            className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-xs text-[var(--primary)] transition-colors hover:bg-[var(--table-row-hover)]"
            onClick={handleCreate}
          >
            <Plus className="h-3 w-3" />
            New Watchlist
          </button>
        </div>
      )}

      {/* Click-outside to close */}
      {open && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setOpen(false)}
          onKeyDown={() => {}}
          role="presentation"
        />
      )}
    </div>
  );
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

  // Stable time window for sparklines / change calc
  const { start, end } = useMemo(() => {
    const now = new Date();
    return {
      start: roundTo5Min(new Date(now.getTime() - 24 * 60 * 60 * 1000)),
      end: roundTo5Min(now),
    };
  }, []);

  // Fetch history for change calculation & day range
  const historyResults = useQueries({
    queries: (instruments ?? [])
      .slice(0, 30)
      .map((inst) => priceHistoryQueryOptions(fundSlug, inst.ticker, start, end)),
  });

  // Build rows with instrument + price data merged
  const rows = useMemo(() => {
    if (!instruments) return [] as WatchlistRow[];
    return instruments.slice(0, 30).map((inst, i) => {
      const price = priceResults[i]?.data;
      const history = historyResults[i]?.data;

      const bid = price ? Number(price.bid) : 0;
      const ask = price ? Number(price.ask) : 0;
      const mid = price ? Number(price.mid) : 0;
      const volume = price?.volume ? Number(price.volume) : 0;

      // Compute day high/low from history
      let dayHigh = 0;
      let dayLow = 0;
      let vwap = 0;
      if (history && history.length > 0) {
        const mids = history.map((p) => Number(p.mid));
        dayHigh = Math.max(...mids);
        dayLow = Math.min(...mids);

        // Approximate VWAP from available data (volume-weighted if volume exists, else simple average)
        const volumes = history.map((p) => (p.volume ? Number(p.volume) : 0));
        const totalVol = volumes.reduce((a, b) => a + b, 0);
        if (totalVol > 0) {
          vwap =
            mids.reduce((acc, m, idx) => acc + m * volumes[idx], 0) / totalVol;
        } else {
          vwap = mids.reduce((a, b) => a + b, 0) / mids.length;
        }
      }

      // Change from earliest history point
      let change = 0;
      let changePct = 0;
      if (history && history.length > 0 && mid > 0) {
        const openMid = Number(history[0].mid);
        change = mid - openMid;
        changePct = openMid !== 0 ? (change / openMid) * 100 : 0;
      }

      return {
        ticker: inst.ticker,
        name: inst.name,
        sector: inst.sector ?? "",
        currency: inst.currency,
        lastPrice: mid,
        change,
        changePct,
        bid,
        ask,
        volume,
        vwap,
        dayHigh,
        dayLow,
        timestamp: price?.timestamp ?? "",
      } satisfies WatchlistRow;
    });
  }, [instruments, priceResults, historyResults]);

  // Watchlist filtering
  const { watchlists, activeWatchlistId, addTicker, removeTicker } =
    useWatchlistStore();
  const activeWatchlist = watchlists.find((w) => w.id === activeWatchlistId);

  const filteredRows = useMemo(() => {
    if (!activeWatchlist) return rows;
    return rows.filter((r) => activeWatchlist.tickers.includes(r.ticker));
  }, [rows, activeWatchlist]);

  const table = useTableState({
    data: filteredRows as unknown as Record<string, unknown>[],
    initialSort: { key: "ticker", direction: "asc" },
    pageSize: 30,
    searchKeys: ["ticker", "name", "sector"],
  });

  // Only one row expanded at a time
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const toggleExpand = useCallback((ticker: string) => {
    setExpandedTicker((prev) => (prev === ticker ? null : ticker));
  }, []);

  if (isLoading) {
    return <TableSkeleton rows={6} columns={5} />;
  }

  return (
    <SectionPanel
      title="Watchlist"
      actions={
        <div className="flex items-center gap-2">
          <WatchlistSelector />
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
        <table className="min-w-full divide-y divide-[var(--border)] text-xs">
          <thead>
            <tr className="text-left text-[var(--muted-foreground)]">
              <th scope="col" className="w-6 whitespace-nowrap px-1 py-1" />
              {activeWatchlistId && <th scope="col" className="w-6 whitespace-nowrap px-1 py-1" />}
              <SortableHeader
                label="Ticker"
                sortKey="ticker"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Last"
                sortKey="lastPrice"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Chg"
                sortKey="change"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Chg %"
                sortKey="changePct"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Bid"
                sortKey="bid"
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
                label="Volume"
                sortKey="volume"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="VWAP"
                sortKey="vwap"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="High"
                sortKey="dayHigh"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <SortableHeader
                label="Low"
                sortKey="dayLow"
                currentSort={table.sortKey}
                direction={table.sortDirection}
                onSort={table.onSort}
              />
              <th scope="col" className="whitespace-nowrap px-2 py-1 text-xs font-semibold">Daily Range</th>
              <th scope="col" className="whitespace-nowrap px-2 py-1 text-right text-xs font-semibold">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {table.rows.map((row) => {
              const r = row as unknown as WatchlistRow;
              const isExpanded = expandedTicker === r.ticker;
              const changeColor =
                r.change > 0
                  ? "text-[var(--success)]"
                  : r.change < 0
                    ? "text-[var(--destructive)]"
                    : "text-[var(--muted-foreground)]";

              return (
                <ExpandableRow
                  key={r.ticker}
                  row={r}
                  isExpanded={isExpanded}
                  changeColor={changeColor}
                  history={historyResults[
                    instruments!.slice(0, 30).findIndex((inst) => inst.ticker === r.ticker)
                  ]?.data}
                  onToggle={toggleExpand}
                  isInWatchlist={
                    activeWatchlist
                      ? activeWatchlist.tickers.includes(r.ticker)
                      : null
                  }
                  onToggleStar={
                    activeWatchlist
                      ? (ticker: string) => {
                          if (activeWatchlist.tickers.includes(ticker)) {
                            removeTicker(activeWatchlist.id, ticker);
                          } else {
                            addTicker(activeWatchlist.id, ticker);
                          }
                        }
                      : null
                  }
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {table.totalPages > 1 && (
        <div className="border-t border-[var(--border)] px-3 py-2">
          <TablePagination
            page={table.page}
            totalPages={table.totalPages}
            totalItems={table.totalFiltered}
            pageSize={table.pageSize}
            onPageChange={table.setPage}
          />
        </div>
      )}
    </SectionPanel>
  );
}
