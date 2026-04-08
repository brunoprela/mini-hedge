"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { instrumentsQueryOptions } from "@/features/instruments/api";
import { Can } from "@/shared/components/can";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useExportCSV } from "@/shared/hooks/use-export-csv";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useTableState } from "@/shared/hooks/use-table-state";
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

type GroupBy = "none" | "sector" | "asset_class";

export function PositionTable({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: positions, isLoading } = usePositions(portfolioId);
  const { data: instruments } = useQuery(instrumentsQueryOptions(fundSlug));
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [showTradeTicket, setShowTradeTicket] = useState(false);
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const exportCSV = useExportCSV();

  // Build instrument lookup for grouping
  const instrumentMap = useMemo(() => {
    if (!instruments) return new Map<string, { sector: string; asset_class: string }>();
    const map = new Map<string, { sector: string; asset_class: string }>();
    for (const inst of instruments) {
      map.set(inst.ticker, {
        sector: inst.sector ?? "Other",
        asset_class: inst.asset_class ?? "Other",
      });
    }
    return map;
  }, [instruments]);

  const handleExport = () => {
    if (!positions || positions.length === 0) return;
    const exportData = positions.map((p) => ({
      instrument: p.instrument_id,
      quantity: p.quantity,
      avg_cost: p.avg_cost,
      market_price: p.market_price,
      market_value: p.market_value,
      unrealized_pnl: p.unrealized_pnl,
      last_updated: p.last_updated,
    }));
    exportCSV(exportData as unknown as Record<string, unknown>[], `positions-${portfolioId}`);
  };

  const totals = useMemo(() => {
    if (!positions || positions.length === 0) return null;
    return positions.reduce(
      (acc, p) => ({
        market_value: acc.market_value + Number(p.market_value),
        unrealized_pnl: acc.unrealized_pnl + Number(p.unrealized_pnl),
        count: acc.count + 1,
      }),
      { market_value: 0, unrealized_pnl: 0, count: 0 },
    );
  }, [positions]);

  const table = useTableState<Record<string, unknown>>({
    data: (positions ?? []) as unknown as Record<string, unknown>[],
    initialSort: { key: "instrument_id", direction: "asc" },
    pageSize: 15,
    searchKeys: ["instrument_id"],
  });

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading positions...</p>;
  }

  return (
    <>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <TableSearch
            value={table.search}
            onChange={table.setSearch}
            placeholder="Search instruments..."
          />
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              Group:
            </span>
            {(["none", "sector", "asset_class"] as const).map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setGroupBy(g)}
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium transition-colors ${
                  groupBy === g
                    ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                {g === "none" ? "None" : g === "sector" ? "Sector" : "Asset Class"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium text-[var(--muted-foreground)]">
            {table.totalFiltered} results
          </span>
          <button
            type="button"
            onClick={handleExport}
            title="Export to CSV"
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
          <Can permission={Permission.TRADES_EXECUTE}>
            <button
              type="button"
              onClick={() => setShowTradeTicket(true)}
              className="rounded-md bg-[var(--foreground)] px-3 py-1.5 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90"
            >
              New Trade
            </button>
          </Can>
        </div>
      </div>

      {/* Totals summary strip */}
      {totals && (
        <div className="mb-3 flex gap-3">
          <div className="flex-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Positions</p>
            <p className="font-mono text-sm font-semibold">{totals.count}</p>
          </div>
          <div className="flex-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Market Value</p>
            <p className="font-mono text-sm font-semibold">{formatPnL(String(totals.market_value))}</p>
          </div>
          <div className="flex-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Unrealized P&L</p>
            <p className={`font-mono text-sm font-semibold ${pnlColorClass(String(totals.unrealized_pnl))}`}>
              {formatPnL(String(totals.unrealized_pnl))}
            </p>
          </div>
        </div>
      )}

      {!positions || positions.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          No positions in this portfolio. Execute a trade to get started.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)]">
                <SortableHeader
                  label="Instrument"
                  sortKey="instrument_id"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Qty"
                  sortKey="quantity"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Avg Cost"
                  sortKey="avg_cost"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                  info="Volume-weighted average cost basis per unit"
                />
                <SortableHeader
                  label="Mkt Price"
                  sortKey="market_price"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Mkt Value"
                  sortKey="market_value"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                  info="Current quantity × market price"
                />
                <SortableHeader
                  label="Unrealized P&L"
                  sortKey="unrealized_pnl"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                  info="Market value minus cost basis"
                />
                <SortableHeader
                  label="Updated"
                  sortKey="last_updated"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <th className="px-3 py-1.5 text-right font-medium">Orders</th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                const rows = table.rows as unknown as NonNullable<typeof positions>;
                if (groupBy === "none") {
                  return rows.map((pos) => (
                    <PositionRow
                      key={pos.instrument_id}
                      pos={pos}
                      expanded={expandedRow === pos.instrument_id}
                      onToggle={() =>
                        setExpandedRow(expandedRow === pos.instrument_id ? null : pos.instrument_id)
                      }
                      fundSlug={fundSlug}
                      portfolioId={portfolioId}
                    />
                  ));
                }

                // Grouped rendering
                const groups = new Map<string, NonNullable<typeof positions>>();
                for (const pos of rows) {
                  const inst = instrumentMap.get(pos.instrument_id);
                  const key = groupBy === "sector"
                    ? (inst?.sector ?? "Other")
                    : (inst?.asset_class ?? "Other");
                  const arr = groups.get(key) ?? [];
                  arr.push(pos);
                  groups.set(key, arr);
                }

                const sortedGroups = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
                return sortedGroups.flatMap(([groupName, groupPositions]) => {
                  const groupMv = groupPositions.reduce((s, p) => s + Number(p.market_value), 0);
                  const groupPnl = groupPositions.reduce((s, p) => s + Number(p.unrealized_pnl), 0);
                  return [
                    <tr
                      key={`group-${groupName}`}
                      className="border-b border-[var(--table-border)] bg-[var(--table-header)]"
                    >
                      <td
                        colSpan={5}
                        className="px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-[var(--foreground)]"
                      >
                        {groupName}
                        <span className="ml-2 font-normal text-[var(--muted-foreground)]">
                          ({groupPositions.length})
                        </span>
                      </td>
                      <td className="px-4 py-1.5 text-right font-mono text-xs font-bold">
                        {formatPnL(String(groupMv))}
                      </td>
                      <td className={`px-4 py-1.5 text-right font-mono text-xs font-bold ${pnlColorClass(String(groupPnl))}`}>
                        {formatPnL(String(groupPnl))}
                      </td>
                      <td className="px-4 py-1.5" />
                    </tr>,
                    ...groupPositions.map((pos) => (
                      <PositionRow
                        key={pos.instrument_id}
                        pos={pos}
                        expanded={expandedRow === pos.instrument_id}
                        onToggle={() =>
                          setExpandedRow(expandedRow === pos.instrument_id ? null : pos.instrument_id)
                        }
                        fundSlug={fundSlug}
                        portfolioId={portfolioId}
                      />
                    )),
                  ];
                });
              })()}
            </tbody>
            {totals && (
              <tfoot>
                <tr className="border-t-2 border-[var(--border)] bg-[var(--table-header)]">
                  <td className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Total ({totals.count})
                  </td>
                  <td className="px-3 py-1.5" />
                  <td className="px-3 py-1.5" />
                  <td className="px-3 py-1.5" />
                  <td className="px-3 py-1.5 text-right font-mono font-semibold">
                    {formatPnL(String(totals.market_value))}
                  </td>
                  <td className={`px-3 py-1.5 text-right font-mono font-semibold ${pnlColorClass(String(totals.unrealized_pnl))}`}>
                    {formatPnL(String(totals.unrealized_pnl))}
                  </td>
                  <td className="px-3 py-1.5" />
                  <td className="px-3 py-1.5" />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}

      {table.totalPages > 1 && (
        <div className="mt-3">
          <TablePagination
            page={table.page}
            totalPages={table.totalPages}
            totalItems={table.totalFiltered}
            pageSize={table.pageSize}
            onPageChange={table.setPage}
          />
        </div>
      )}

      {showTradeTicket && (
        <TradeTicket portfolioId={portfolioId} onClose={() => setShowTradeTicket(false)} />
      )}
    </>
  );
}

// ─── Sub-component ─────────────────────────────────────────

function PositionRow({
  pos,
  expanded,
  onToggle,
  fundSlug,
  portfolioId,
}: {
  pos: { instrument_id: string; quantity: string; avg_cost: string; market_price: string; market_value: string; unrealized_pnl: string; last_updated: string };
  expanded: boolean;
  onToggle: () => void;
  fundSlug: string;
  portfolioId: string;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
      >
        <td className="px-3 py-1.5 font-mono font-medium">
          {pos.instrument_id}
          <span className="ml-1 text-xs text-[var(--muted-foreground)]">
            {expanded ? "▼" : "▶"}
          </span>
        </td>
        <td className="px-3 py-1.5 text-right">{formatQuantity(pos.quantity)}</td>
        <td className="px-3 py-1.5 text-right">{formatPrice(pos.avg_cost)}</td>
        <td className="px-3 py-1.5 text-right">{formatPrice(pos.market_price)}</td>
        <td className="px-3 py-1.5 text-right">{formatPnL(pos.market_value)}</td>
        <td className={`px-3 py-1.5 text-right font-medium ${pnlColorClass(pos.unrealized_pnl)}`}>
          {formatPnL(pos.unrealized_pnl)}
        </td>
        <td className="px-3 py-1.5 text-right text-[var(--muted-foreground)]">
          {formatTimestamp(pos.last_updated)}
        </td>
        <td className="px-3 py-1.5 text-right">
          <Link
            href={`/${fundSlug}/portfolio/${portfolioId}#orders`}
            className="text-[var(--foreground)] underline-offset-2 hover:underline"
          >
            Orders &rarr;
          </Link>
        </td>
      </tr>
      {expanded && (
        <LotDrawer portfolioId={portfolioId} instrumentId={pos.instrument_id} />
      )}
    </>
  );
}
