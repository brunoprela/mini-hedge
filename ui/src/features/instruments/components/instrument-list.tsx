"use client";

import { SectionPanel } from "@/shared/components/section-panel";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useTableState } from "@/shared/hooks/use-table-state";
import { useInstruments } from "../hooks/use-instruments";

export function InstrumentList() {
  const allQuery = useInstruments();
  const instruments = allQuery.data;
  const isLoading = allQuery.isLoading;

  const table = useTableState({
    data: (instruments ?? []) as unknown as Record<string, unknown>[],
    initialSort: { key: "ticker", direction: "asc" },
    pageSize: 25,
    searchKeys: ["ticker", "name", "sector", "asset_class", "currency", "country"],
  });

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>;
  }

  return (
    <div className="space-y-3">
      <SectionPanel
        title="Instruments"
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
                <SortableHeader
                  label="Name"
                  sortKey="name"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Class"
                  sortKey="asset_class"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Sector"
                  sortKey="sector"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Exchange"
                  sortKey="exchange"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Currency"
                  sortKey="currency"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
                <SortableHeader
                  label="Country"
                  sortKey="country"
                  currentSort={table.sortKey}
                  direction={table.sortDirection}
                  onSort={table.onSort}
                />
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => {
                const inst = row as Record<string, unknown>;
                return (
                  <tr
                    key={inst.id as string}
                    className="border-b border-[var(--table-border)] last:border-0 hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-1.5 font-mono text-sm font-medium text-[var(--foreground)]">
                      {inst.ticker as string}
                    </td>
                    <td className="max-w-[200px] truncate px-3 py-1.5 text-xs">
                      {inst.name as string}
                    </td>
                    <td className="px-3 py-1.5 text-xs">
                      <span className="rounded-full bg-[var(--muted)] px-2 py-0.5 text-[10px] font-medium">
                        {inst.asset_class as string}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                      {(inst.sector as string) || "—"}
                    </td>
                    <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                      {inst.exchange as string}
                    </td>
                    <td className="px-3 py-1.5 text-xs font-mono">{inst.currency as string}</td>
                    <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                      {(inst.country as string) || "—"}
                    </td>
                  </tr>
                );
              })}
              {table.rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                    No instruments found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </SectionPanel>

      {table.totalPages > 1 && (
        <TablePagination
          page={table.page}
          totalPages={table.totalPages}
          totalItems={table.totalFiltered}
          pageSize={table.pageSize}
          onPageChange={table.setPage}
        />
      )}
    </div>
  );
}
