"use client";

import { useCallback } from "react";

/**
 * Generates a CSV string from an array of objects and triggers a file download.
 */
function arrayToCSV(data: Record<string, unknown>[]): string {
  if (data.length === 0) return "";

  const headers = Object.keys(data[0]);
  const rows = data.map((row) =>
    headers
      .map((h) => {
        const val = row[h];
        if (val == null) return "";
        const str = String(val);
        // Escape quotes and wrap in quotes if the value contains comma, quote, or newline
        if (str.includes(",") || str.includes('"') || str.includes("\n")) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      })
      .join(","),
  );

  return [headers.join(","), ...rows].join("\n");
}

function downloadCSV(csv: string, filename: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename.endsWith(".csv") ? filename : `${filename}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Hook that returns a function to export an array of objects as a CSV download.
 *
 * Usage:
 * ```
 * const exportCSV = useExportCSV();
 * exportCSV(data, "orders");
 * ```
 */
export function useExportCSV() {
  return useCallback((data: Record<string, unknown>[], filename: string) => {
    if (data.length === 0) return;
    const csv = arrayToCSV(data);
    downloadCSV(csv, filename);
  }, []);
}
