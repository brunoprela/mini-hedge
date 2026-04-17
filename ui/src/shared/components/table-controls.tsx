"use client";

import { Pagination, Tooltip } from "@mini-hedge/ui";
import { ChevronDown, ChevronUp, Info, Search } from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  SortableHeader                                                            */
/* -------------------------------------------------------------------------- */

interface SortableHeaderProps<T> {
  label: string;
  sortKey: T;
  currentSort: T | null;
  direction: "asc" | "desc";
  onSort: (key: T) => void;
  info?: string;
}

export function SortableHeader<T>({
  label,
  sortKey,
  currentSort,
  direction,
  onSort,
  info,
}: SortableHeaderProps<T>) {
  const isActive = currentSort === sortKey;
  const Arrow = isActive && direction === "desc" ? ChevronDown : ChevronUp;

  return (
    <th
      onClick={() => onSort(sortKey)}
      className="cursor-pointer select-none px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <Arrow
          className={`h-3.5 w-3.5 ${
            isActive ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)] opacity-30"
          }`}
        />
        {info && <InfoTooltip text={info} />}
      </span>
    </th>
  );
}

/* -------------------------------------------------------------------------- */
/*  TableSearch                                                               */
/* -------------------------------------------------------------------------- */

interface TableSearchProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function TableSearch({ value, onChange, placeholder = "Search..." }: TableSearchProps) {
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)]" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-md border border-[var(--border)] bg-[var(--input)] pl-9 pr-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  TablePagination                                                           */
/* -------------------------------------------------------------------------- */

interface TablePaginationProps {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (p: number) => void;
}

/**
 * Thin wrapper over the shared `Pagination` primitive. Kept for backwards compatibility
 * with existing `TablePagination` call sites; new code can import `Pagination` directly
 * from `@mini-hedge/ui`.
 */
export function TablePagination({
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: TablePaginationProps) {
  return (
    <Pagination
      page={page}
      totalPages={totalPages}
      totalItems={totalItems}
      pageSize={pageSize}
      onPageChange={onPageChange}
    />
  );
}

/* -------------------------------------------------------------------------- */
/*  InfoTooltip                                                               */
/* -------------------------------------------------------------------------- */

interface InfoTooltipProps {
  text: string;
}

export function InfoTooltip({ text }: InfoTooltipProps) {
  return (
    <Tooltip content={text}>
      <Info className="h-3.5 w-3.5 text-[var(--muted-foreground)] cursor-help" />
    </Tooltip>
  );
}
