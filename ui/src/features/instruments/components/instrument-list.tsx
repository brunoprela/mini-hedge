"use client";

import { useState } from "react";
import { useInstrumentSearch, useInstruments } from "../hooks/use-instruments";

export function InstrumentList() {
  const [search, setSearch] = useState("");

  const allQuery = useInstruments();
  const searchQuery = useInstrumentSearch(search);

  const instruments = search.length >= 1 ? searchQuery.data : allQuery.data;
  const isLoading = search.length >= 1 ? searchQuery.isLoading : allQuery.isLoading;

  return (
    <div className="space-y-4">
      <input
        type="text"
        placeholder="Search instruments..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-sm rounded-md border border-[var(--border)] px-3 py-2 text-sm"
      />

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
                <th className="px-4 py-2 text-left font-medium">Ticker</th>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Class</th>
                <th className="px-4 py-2 text-left font-medium">Exchange</th>
                <th className="px-4 py-2 text-left font-medium">Currency</th>
              </tr>
            </thead>
            <tbody>
              {instruments?.map((inst) => (
                <tr key={inst.id} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-4 py-2 font-mono font-medium">{inst.ticker}</td>
                  <td className="px-4 py-2">{inst.name}</td>
                  <td className="px-4 py-2">{inst.asset_class}</td>
                  <td className="px-4 py-2">{inst.exchange}</td>
                  <td className="px-4 py-2">{inst.currency}</td>
                </tr>
              ))}
              {instruments?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted-foreground)]">
                    No instruments found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
