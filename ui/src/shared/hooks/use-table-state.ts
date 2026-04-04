"use client";

import { useMemo, useState } from "react";

interface UseTableStateOptions<T> {
  data: T[];
  initialSort?: { key: keyof T; direction: "asc" | "desc" };
  pageSize?: number;
  searchKeys?: (keyof T)[];
}

interface TableState<T> {
  rows: T[];
  totalFiltered: number;
  sortKey: keyof T | null;
  sortDirection: "asc" | "desc";
  onSort: (key: keyof T) => void;
  search: string;
  setSearch: (v: string) => void;
  page: number;
  setPage: (p: number) => void;
  pageSize: number;
  totalPages: number;
}

export function useTableState<T extends Record<string, unknown>>(
  options: UseTableStateOptions<T>,
): TableState<T> {
  const { data, initialSort, pageSize: pageSizeOption = 25, searchKeys = [] } = options;

  const [sortKey, setSortKey] = useState<keyof T | null>(initialSort?.key ?? null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">(
    initialSort?.direction ?? "asc",
  );
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const onSort = (key: keyof T) => {
    if (key === sortKey) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
    setPage(0);
  };

  const handleSetSearch = (v: string) => {
    setSearch(v);
    setPage(0);
  };

  const filtered = useMemo(() => {
    if (!search.trim() || searchKeys.length === 0) return data;
    const term = search.toLowerCase();
    return data.filter((row) =>
      searchKeys.some((key) => {
        const val = row[key];
        if (val == null) return false;
        return String(val).toLowerCase().includes(term);
      }),
    );
  }, [data, search, searchKeys]);

  const sorted = useMemo(() => {
    if (sortKey == null) return filtered;
    const arr = [...filtered];
    arr.sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      const aNum = parseFloat(String(aVal));
      const bNum = parseFloat(String(bVal));

      let cmp: number;
      if (!Number.isNaN(aNum) && !Number.isNaN(bNum)) {
        cmp = aNum - bNum;
      } else {
        cmp = String(aVal).localeCompare(String(bVal));
      }

      return sortDirection === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sortKey, sortDirection]);

  const totalFiltered = sorted.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSizeOption));

  const rows = useMemo(() => {
    const start = page * pageSizeOption;
    return sorted.slice(start, start + pageSizeOption);
  }, [sorted, page, pageSizeOption]);

  return {
    rows,
    totalFiltered,
    sortKey,
    sortDirection,
    onSort,
    search,
    setSearch: handleSetSearch,
    page,
    setPage,
    pageSize: pageSizeOption,
    totalPages,
  };
}
