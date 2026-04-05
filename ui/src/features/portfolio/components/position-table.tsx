"use client";

import { Download } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
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

export function PositionTable({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: positions, isLoading } = usePositions(portfolioId);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [showTradeTicket, setShowTradeTicket] = useState(false);
  const exportCSV = useExportCSV();

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
        <TableSearch
          value={table.search}
          onChange={table.setSearch}
          placeholder="Search instruments..."
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExport}
            title="Export to CSV"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
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
                <th className="px-4 py-2 text-right font-medium">Orders</th>
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => {
                const pos = row as unknown as NonNullable<typeof positions>[number];
                return (
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
                );
              })}
            </tbody>
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
