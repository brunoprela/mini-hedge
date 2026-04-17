"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState, TableSkeleton } from "@mini-hedge/ui";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@mini-hedge/ui";
import { api, fundHeaders } from "@/shared/lib/api-client";

export default function PriceValidationPage() {
  const queryClient = useQueryClient();
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [businessDate, setBusinessDate] = useState(
    new Date().toISOString().slice(0, 10),
  );

  const enabled = !!fundSlug && !!businessDate;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["price-validation", fundSlug, businessDate],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/eod/finalized-prices",
        {
          params: { query: { business_date: businessDate } },
          headers: fundHeaders(fundSlug),
        },
      );
      if (error) throw error;
      return data;
    },
    enabled,
  });

  const overrideMutation = useMutation({
    mutationFn: async (vars: {
      instrument_id: string;
      close_price: number;
    }) => {
      const { data, error } = await api.POST("/api/v1/eod/finalize-price", {
        body: {
          instrument_id: vars.instrument_id,
          business_date: businessDate,
          close_price: vars.close_price,
          source: "manual",
        },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["price-validation"] });
      toast.success("Price override applied");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function handleOverride(row: { instrument_id: string }) {
    const price = prompt(`Override price for ${row.instrument_id}:`);
    if (!price) return;
    overrideMutation.mutate({
      instrument_id: row.instrument_id,
      close_price: Number(price),
    });
  }

  const rows = data ?? [];

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Price Validation</h2>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
          showPortfolio={false}
        />
        <label className="block">
          <span className="block text-xs text-[var(--muted-foreground)] mb-1">
            Business Date
          </span>
          <input
            type="date"
            value={businessDate}
            onChange={(e) => setBusinessDate(e.target.value)}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
          />
        </label>
      </div>

      {!fundSlug && (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund to view finalized prices.
        </p>
      )}

      {fundSlug && isLoading && <TableSkeleton rows={6} columns={7} />}

      {fundSlug && isError && (
        <ErrorState message={error.message} onRetry={refetch} />
      )}

      {fundSlug && !isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-3">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Finalized
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {rows.length}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Manual Overrides
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {rows.filter((r) => r.source === "manual").length}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Business Date
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {businessDate}
              </dd>
            </div>
          </dl>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Instrument
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Close Price
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Source
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Finalized By
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {rows.map((row) => (
                  <tr
                    key={row.instrument_id}
                    className="transition-colors hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-3 py-2 text-sm font-medium">
                      {row.instrument_id}
                    </td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {row.close_price}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <StatusBadge
                        label={row.source}
                        variant={row.source === "manual" ? "warning" : "neutral"}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                      {row.finalized_by}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <button
                        type="button"
                        disabled={overrideMutation.isPending}
                        onClick={() => handleOverride(row)}
                        className="flex items-center gap-1 rounded bg-[var(--primary)] px-2 py-1 text-xs text-white hover:opacity-90 disabled:opacity-50"
                      >
                        {overrideMutation.isPending && (
                          <Loader2 size={12} className="animate-spin" />
                        )}
                        Override
                      </button>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]"
                    >
                      No finalized prices found for this date.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
