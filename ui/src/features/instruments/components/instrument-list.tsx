"use client";

import { TableSkeleton } from "@mini-hedge/ui";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { InstrumentLink } from "@/shared/components/instrument-link";
import { SectionPanel } from "@/shared/components/section-panel";
import { SortableHeader, TablePagination, TableSearch } from "@/shared/components/table-controls";
import { useTableState } from "@/shared/hooks/use-table-state";
import { useInstruments } from "../hooks/use-instruments";
import { InstrumentDetailPanel } from "./instrument-detail-panel";

type GroupBy = "none" | "sector" | "industry" | "country" | "asset_class";

const GROUP_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "none", label: "None" },
  { value: "sector", label: "Sector" },
  { value: "industry", label: "Industry" },
  { value: "country", label: "Country" },
  { value: "asset_class", label: "Asset Class" },
];

export function InstrumentList() {
  const allQuery = useInstruments();
  const instruments = allQuery.data;
  const isLoading = allQuery.isLoading;

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const table = useTableState({
    data: (instruments ?? []) as unknown as Record<string, unknown>[],
    initialSort: { key: "ticker", direction: "asc" },
    pageSize: 25,
    searchKeys: ["ticker", "name", "sector", "asset_class", "currency", "country"],
  });

  const selectedInstrument = useMemo(() => {
    if (!selectedId || !instruments) return null;
    return instruments.find((i) => i.id === selectedId) ?? null;
  }, [selectedId, instruments]);

  const toggleGroup = (groupName: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupName)) {
        next.delete(groupName);
      } else {
        next.add(groupName);
      }
      return next;
    });
  };

  // Build groups from current table rows (already filtered/sorted/paged)
  const groupedRows = useMemo(() => {
    if (groupBy === "none") return null;

    const rows = table.rows as Record<string, unknown>[];
    const groups = new Map<string, Record<string, unknown>[]>();
    for (const row of rows) {
      const key = (row[groupBy] as string) || "Unknown";
      const arr = groups.get(key) ?? [];
      arr.push(row);
      groups.set(key, arr);
    }

    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [table.rows, groupBy]);

  if (isLoading) {
    return <TableSkeleton rows={8} columns={6} />;
  }

  const renderRow = (inst: Record<string, unknown>) => {
    const id = inst.id as string;
    const isSelected = selectedId === id;
    return (
      <tr
        key={id}
        onClick={() => setSelectedId(isSelected ? null : id)}
        className={`cursor-pointer hover:bg-[var(--table-row-hover)] ${
          isSelected ? "ring-1 ring-inset ring-[var(--primary)]" : ""
        }`}
      >
        <td className="px-3 py-1.5 text-sm">
          <InstrumentLink instrument={inst.ticker as string} />
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
          {(inst.sector as string) || "\u2014"}
        </td>
        <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
          {inst.exchange as string}
        </td>
        <td className="px-3 py-1.5 text-xs font-mono">{inst.currency as string}</td>
        <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
          {(inst.country as string) || "\u2014"}
        </td>
      </tr>
    );
  };

  return (
    <div className="flex gap-3">
      <div className="min-w-0 flex-1 space-y-3">
        <SectionPanel
          title="Instruments"
          actions={
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                  Group:
                </span>
                {GROUP_OPTIONS.map((g) => (
                  <button
                    key={g.value}
                    type="button"
                    onClick={() => {
                      setGroupBy(g.value);
                      setCollapsedGroups(new Set());
                    }}
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium transition-colors ${
                      groupBy === g.value
                        ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                        : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
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
            <table className="min-w-full divide-y divide-[var(--border)] text-sm">
              <thead>
                <tr className="text-left text-[var(--muted-foreground)]">
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
              <tbody className="divide-y divide-[var(--table-border)]">
                {groupBy === "none" ? (
                  <>
                    {table.rows.map((row) => renderRow(row as Record<string, unknown>))}
                    {table.rows.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                          No instruments found
                        </td>
                      </tr>
                    )}
                  </>
                ) : (
                  <>
                    {groupedRows && groupedRows.length > 0 ? (
                      groupedRows.flatMap(([groupName, groupInstruments]) => {
                        const isCollapsed = collapsedGroups.has(groupName);
                        return [
                          <tr
                            key={`group-${groupName}`}
                            onClick={() => toggleGroup(groupName)}
                            className="cursor-pointer bg-[var(--table-header)] hover:bg-[var(--table-row-hover)]"
                          >
                            <td
                              colSpan={7}
                              className="px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-[var(--foreground)]"
                            >
                              <span className="inline-flex items-center gap-1.5">
                                {isCollapsed ? (
                                  <ChevronRight className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
                                ) : (
                                  <ChevronDown className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
                                )}
                                {groupName}
                                <span className="font-normal text-[var(--muted-foreground)]">
                                  ({groupInstruments.length})
                                </span>
                              </span>
                            </td>
                          </tr>,
                          ...(!isCollapsed
                            ? groupInstruments.map((inst) => renderRow(inst))
                            : []),
                        ];
                      })
                    ) : (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                          No instruments found
                        </td>
                      </tr>
                    )}
                  </>
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

      {/* Instrument detail side panel */}
      {selectedInstrument && (
        <InstrumentDetailPanel
          instrument={selectedInstrument}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
