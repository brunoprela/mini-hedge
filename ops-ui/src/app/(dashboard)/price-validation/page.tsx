"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/shared/components/error-state";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";

interface FinalizedPrice {
  instrument_id: string;
  ticker: string;
  source_price: string;
  finalized_price: string;
  spread_pct: number;
  is_stale: boolean;
  finalized_at: string;
}

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
    queryFn: () =>
      apiFetch<FinalizedPrice[]>(
        `eod/finalized-prices?fund_slug=${fundSlug}&business_date=${businessDate}`,
      ),
    enabled,
  });

  const overrideMutation = useMutation({
    mutationFn: (vars: {
      instrument_id: string;
      override_price: number;
      reason: string;
    }) =>
      apiFetch("eod/finalize-price", {
        method: "POST",
        body: JSON.stringify({
          fund_slug: fundSlug,
          instrument_id: vars.instrument_id,
          override_price: vars.override_price,
          reason: vars.reason,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["price-validation"] });
      toast.success("Price override applied");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function handleOverride(row: FinalizedPrice) {
    const price = prompt(`Override price for ${row.ticker}:`);
    if (!price) return;
    const reason = prompt("Reason for override:");
    if (!reason) return;
    overrideMutation.mutate({
      instrument_id: row.instrument_id,
      override_price: Number(price),
      reason,
    });
  }

  const rows = data ?? [];
  const staleCount = rows.filter((r) => r.is_stale).length;
  const highSpreadCount = rows.filter((r) => r.spread_pct > 5).length;
  const lastFinalized =
    rows.length > 0
      ? rows.reduce((latest, r) =>
          r.finalized_at > latest.finalized_at ? r : latest,
        ).finalized_at
      : null;

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

      {fundSlug && isLoading && (
        <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
          Loading...
        </p>
      )}

      {fundSlug && isError && (
        <ErrorState message={error.message} onRetry={refetch} />
      )}

      {fundSlug && !isLoading && !isError && (
        <>
          {/* KPI strip */}
          <dl className="mb-6 grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-4">
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Total Instruments
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {rows.length}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Stale Prices
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {staleCount}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                High Spread (&gt;5%)
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {highSpreadCount}
              </dd>
            </div>
            <div className="bg-[var(--card)] px-4 py-4">
              <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Last Finalized
              </dt>
              <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
                {lastFinalized
                  ? new Date(lastFinalized).toLocaleString()
                  : "—"}
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
                    Ticker
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Source Price
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Finalized Price
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Spread %
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Stale
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]"
                  >
                    Finalized At
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
                      {row.ticker}
                    </td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {row.source_price}
                    </td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {row.finalized_price}
                    </td>
                    <td className="px-3 py-2 text-sm text-right font-mono">
                      {row.spread_pct.toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-sm">
                      {row.is_stale ? (
                        <StatusBadge label="Stale" variant="danger" />
                      ) : (
                        <StatusBadge label="Fresh" variant="success" />
                      )}
                    </td>
                    <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                      {new Date(row.finalized_at).toLocaleString()}
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
                      colSpan={7}
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
