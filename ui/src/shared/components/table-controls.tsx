"use client";

import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Info, Search } from "lucide-react";
import { useState } from "react";

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
        className="h-9 w-full rounded-lg border border-[var(--border)] bg-[var(--input)] pl-9 pr-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
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

export function TablePagination({
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: TablePaginationProps) {
  const start = page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, totalItems);

  // Build visible page numbers: always show first, last, and pages around current
  const pages: (number | "ellipsis")[] = [];
  for (let i = 0; i < totalPages; i++) {
    if (i === 0 || i === totalPages - 1 || (i >= page - 1 && i <= page + 1)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "ellipsis") {
      pages.push("ellipsis");
    }
  }

  return (
    <div className="flex items-center justify-between text-sm text-[var(--muted-foreground)]">
      <span>
        Showing {start}–{end} of {totalItems} results
      </span>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--accent)] transition-colors"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        {pages.map((p, idx) =>
          p === "ellipsis" ? (
            // biome-ignore lint/suspicious/noArrayIndexKey: ellipsis items have no stable key
            <span key={`ellipsis-${idx}`} className="px-1">
              ...
            </span>
          ) : (
            <button
              type="button"
              key={p}
              onClick={() => onPageChange(p)}
              className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-sm transition-colors ${
                p === page
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)] font-medium"
                  : "border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] hover:bg-[var(--accent)]"
              }`}
            >
              {p + 1}
            </button>
          ),
        )}

        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages - 1}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--accent)] transition-colors"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  InfoTooltip                                                               */
/* -------------------------------------------------------------------------- */

interface InfoTooltipProps {
  text: string;
}

export function InfoTooltip({ text }: InfoTooltipProps) {
  const [show, setShow] = useState(false);

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: tooltip trigger needs hover
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <Info className="h-3.5 w-3.5 text-[var(--muted-foreground)] cursor-help" />
      {show && (
        <span className="absolute bottom-full left-1/2 z-50 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-md bg-[var(--popover)] px-2.5 py-1.5 text-xs text-[var(--popover-foreground)] shadow-md border border-[var(--border)]">
          {text}
        </span>
      )}
    </span>
  );
}
