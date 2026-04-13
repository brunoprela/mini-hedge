"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorState } from "@/shared/components/error-state";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
import type { CashBalance, SettlementRecord, SettlementLadder } from "@/shared/types";

type Tab = "balances" | "settlements" | "ladder";

const SETTLEMENT_STATUS_VARIANT: Record<string, "warning" | "neutral" | "success" | "danger"> = {
  pending: "warning",
  settled: "success",
  failed: "danger",
};

const fmt = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 });

export default function CashPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("balances");

  const enabled = !!portfolioId;

  const {
    data: balances,
    isLoading: balancesLoading,
    isError: balancesError,
    error: balancesErr,
    refetch: refetchBalances,
  } = useQuery({
    queryKey: ["cash", "balances", portfolioId],
    queryFn: () => apiFetch<CashBalance[]>(`cash/${portfolioId}/balances`),
    enabled,
  });

  const {
    data: settlements,
    isLoading: settlementsLoading,
    isError: settlementsError,
    error: settlementsErr,
    refetch: refetchSettlements,
  } = useQuery({
    queryKey: ["cash", "settlements", portfolioId],
    queryFn: () => apiFetch<SettlementRecord[]>(`cash/${portfolioId}/settlements`),
    enabled,
  });

  const {
    data: ladder,
    isLoading: ladderLoading,
    isError: ladderError,
    error: ladderErr,
    refetch: refetchLadder,
  } = useQuery({
    queryKey: ["cash", "ladder", portfolioId],
    queryFn: () => apiFetch<SettlementLadder>(`cash/${portfolioId}/ladder`),
    enabled,
  });

  const isLoading =
    (activeTab === "balances" && balancesLoading) ||
    (activeTab === "settlements" && settlementsLoading) ||
    (activeTab === "ladder" && ladderLoading);

  const isError =
    (activeTab === "balances" && balancesError) ||
    (activeTab === "settlements" && settlementsError) ||
    (activeTab === "ladder" && ladderError);

  const errorMessage =
    (activeTab === "balances" ? balancesErr?.message : undefined) ??
    (activeTab === "settlements" ? settlementsErr?.message : undefined) ??
    (activeTab === "ladder" ? ladderErr?.message : undefined) ??
    "Something went wrong";

  const handleRetry = () => {
    if (activeTab === "balances") refetchBalances();
    if (activeTab === "settlements") refetchSettlements();
    if (activeTab === "ladder") refetchLadder();
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "balances", label: "Balances" },
    { key: "settlements", label: "Settlements" },
    { key: "ladder", label: "Ladder" },
  ];

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Cash & Settlement</h2>

      <div className="mb-6">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
        />
      </div>

      {!portfolioId && (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund and portfolio to view cash data.
        </p>
      )}

      {portfolioId && (
        <>
          {/* Tab toggle */}
          <div className="mb-4 flex gap-1 rounded-lg border border-[var(--border)] p-1 w-fit">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {isLoading && (
            <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
          )}

          {isError && (
            <ErrorState message={errorMessage} onRetry={handleRetry} />
          )}

          {/* Balances tab */}
          {activeTab === "balances" && !balancesLoading && !balancesError && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-[var(--border)]">
                <thead>
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Currency</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Available</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Pending In</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Pending Out</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--table-border)]">
                  {balances?.map((b) => (
                    <tr key={b.currency} className="transition-colors hover:bg-[var(--table-row-hover)]">
                      <td className="px-3 py-2 text-sm font-medium">{b.currency}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono">{fmt(b.available_balance)}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono">{fmt(b.pending_inflows)}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono">{fmt(b.pending_outflows)}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono font-semibold">{fmt(b.total_balance)}</td>
                    </tr>
                  ))}
                  {balances?.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                        No balances found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Settlements tab */}
          {activeTab === "settlements" && !settlementsLoading && !settlementsError && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-[var(--border)]">
                <thead>
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">ID</th>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Instrument</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Amount</th>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Currency</th>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Settle Date</th>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Trade Date</th>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--table-border)]">
                  {settlements?.map((s) => (
                    <tr key={s.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                      <td className="px-3 py-2 text-sm font-mono" title={s.id}>
                        {s.id.slice(0, 8)}...
                      </td>
                      <td className="px-3 py-2 text-sm font-mono">{s.instrument_id}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono">{fmt(s.settlement_amount)}</td>
                      <td className="px-3 py-2 text-sm">{s.currency}</td>
                      <td className="px-3 py-2 text-sm">{s.settlement_date}</td>
                      <td className="px-3 py-2 text-sm">{s.trade_date}</td>
                      <td className="px-3 py-2 text-sm">
                        <StatusBadge
                          label={s.status}
                          variant={SETTLEMENT_STATUS_VARIANT[s.status] ?? "neutral"}
                        />
                      </td>
                    </tr>
                  ))}
                  {settlements?.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                        No settlements found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Ladder tab */}
          {activeTab === "ladder" && !ladderLoading && !ladderError && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-[var(--border)]">
                <thead>
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Date</th>
                    <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Currency</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Inflows</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Outflows</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Net</th>
                    <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Cumulative</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--table-border)]">
                  {ladder?.entries?.map((entry, i) => (
                    <tr key={`${entry.settlement_date}-${entry.currency}-${i}`} className="transition-colors hover:bg-[var(--table-row-hover)]">
                      <td className="px-3 py-2 text-sm">{entry.settlement_date}</td>
                      <td className="px-3 py-2 text-sm">{entry.currency}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono text-green-600">{fmt(entry.expected_inflow)}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono text-red-600">{fmt(entry.expected_outflow)}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono font-semibold">{fmt(entry.net_flow)}</td>
                      <td className="px-3 py-2 text-sm text-right font-mono font-semibold">{fmt(entry.cumulative_balance)}</td>
                    </tr>
                  ))}
                  {ladder?.entries?.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
                        No ladder entries found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
