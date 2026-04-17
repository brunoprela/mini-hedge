"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Plus, ArrowDownRight } from "lucide-react";
import { api, fundHeaders } from "@/shared/lib/api-client";
import { ErrorState, TableSkeleton } from "@mini-hedge/ui";

/* ── helpers ─────────────────────────────────────────────────────── */

function fmt(value: number | string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(value));
}

function pct(value: number | string, decimals = 2) {
  return `${Number(value).toFixed(decimals)}%`;
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/* ── tabs ────────────────────────────────────────────────────────── */

type Tab = "performance" | "holdings" | "documents";

const tabs: Tab[] = ["performance", "holdings", "documents"];
const tabLabels: Record<Tab, string> = {
  performance: "Performance",
  holdings: "Holdings",
  documents: "Documents",
};

/* ── NAV history row ─────────────────────────────────────────────── */

interface NavRow {
  business_date: string;
  nav: number;
  nav_per_share: number;
}

/* ── main page ───────────────────────────────────────────────────── */

export default function FundDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("performance");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-[var(--foreground-bright)]">
            Fund Detail
          </h1>
          <p className="text-sm text-[var(--muted-foreground)] break-all">{slug}</p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/subscribe?fund=${slug}`}
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-3.5 py-2 min-h-9 text-sm font-medium text-white hover:opacity-90"
          >
            <Plus size={15} />
            Subscribe
          </Link>
          <Link
            href={`/redeem?fund=${slug}`}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3.5 py-2 min-h-9 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--muted)]"
          >
            <ArrowDownRight size={15} />
            Redeem
          </Link>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg border border-[var(--border)] bg-[var(--muted)] p-1 w-full sm:w-fit overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors min-h-11 whitespace-nowrap flex-1 sm:flex-none ${
              activeTab === tab
                ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {tabLabels[tab]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "performance" && <PerformanceTab slug={slug} />}
      {activeTab === "holdings" && <HoldingsTab slug={slug} />}
      {activeTab === "documents" && <DocumentsTab slug={slug} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Performance Tab
   ═══════════════════════════════════════════════════════════════════ */

function PerformanceTab({ slug }: { slug: string }) {
  const {
    data: navHistory,
    isLoading: navLoading,
    error: navError,
  } = useQuery({
    queryKey: ["nav-history", slug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eod/nav/history", {
        params: { query: { period: "90d" } },
        headers: fundHeaders(slug),
      });
      if (error) throw error;
      return data;
    },
  });

  const {
    data: overview,
    isLoading: ovLoading,
    error: ovError,
  } = useQuery({
    queryKey: ["capital-overview", slug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/capital/overview", {
        headers: fundHeaders(slug),
      });
      if (error) throw error;
      return data;
    },
  });

  const isLoading = navLoading || ovLoading;
  const error = navError || ovError;

  if (error) return <ErrorState message={String(error)} />;

  // Sort descending by date for display
  const sorted = navHistory ? [...navHistory].sort((a, b) => b.business_date.localeCompare(a.business_date)) : [];

  const latest = sorted[0];

  return (
    <div className="space-y-6">
      {/* KPI strip */}
      <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 sm:divide-x sm:divide-y-0 divide-y divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Latest NAV
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
            {isLoading ? "—" : latest ? fmt(latest.nav) : "—"}
          </dd>
        </div>
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            NAV / Share
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
            {isLoading ? "—" : latest ? fmt(latest.nav_per_share) : "—"}
          </dd>
        </div>
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Total AUM
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
            {isLoading ? "—" : overview ? fmt(overview.total_aum) : "—"}
          </dd>
        </div>
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Total Investors
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
            {isLoading ? "—" : overview ? overview.total_investors : "—"}
          </dd>
        </div>
      </dl>

      {/* NAV history table */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Date
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                NAV
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                NAV / Share
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Change %
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {isLoading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8">
                  <TableSkeleton rows={4} columns={4} />
                </td>
              </tr>
            ) : sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                >
                  No NAV history available.
                </td>
              </tr>
            ) : (
              sorted.map((row, i) => {
                const prev = sorted[i + 1];
                const change =
                  prev && Number(prev.nav_per_share) !== 0
                    ? ((Number(row.nav_per_share) - Number(prev.nav_per_share)) /
                        Number(prev.nav_per_share)) *
                      100
                    : null;
                return (
                  <tr
                    key={row.business_date}
                    className="hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-4 py-3">{fmtDate(row.business_date)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fmt(row.nav)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fmt(row.nav_per_share)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular-nums ${
                        change === null
                          ? ""
                          : change >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--destructive)]"
                      }`}
                    >
                      {change === null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Holdings Tab
   ═══════════════════════════════════════════════════════════════════ */

function HoldingsTab({ slug }: { slug: string }) {
  const [selectedPortfolio, setSelectedPortfolio] = useState<string | null>(
    null,
  );

  const {
    data: portfolios,
    isLoading: portLoading,
    error: portError,
  } = useQuery({
    queryKey: ["portfolios", slug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/portfolios", {
        headers: fundHeaders(slug),
      });
      if (error) throw error;
      return data;
    },
  });

  // Auto-select first portfolio
  const portfolioId =
    selectedPortfolio ?? (portfolios && portfolios.length > 0 ? portfolios[0].id : null);

  const {
    data: summary,
    isLoading: sumLoading,
    error: sumError,
  } = useQuery({
    queryKey: ["portfolio-summary", portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/portfolios/{portfolio_id}/summary",
        {
          params: { path: { portfolio_id: portfolioId! } },
          headers: fundHeaders(slug),
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!portfolioId,
  });

  const {
    data: positions,
    isLoading: posLoading,
    error: posError,
  } = useQuery({
    queryKey: ["portfolio-positions", portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/portfolios/{portfolio_id}/positions",
        {
          params: { path: { portfolio_id: portfolioId! } },
          headers: fundHeaders(slug),
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!portfolioId,
  });

  const error = portError || sumError || posError;
  if (error) return <ErrorState message={String(error)} />;

  const isLoading = portLoading || sumLoading || posLoading;

  return (
    <div className="space-y-6">
      {/* Portfolio selector */}
      {portfolios && portfolios.length > 1 && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
          <label className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Portfolio
          </label>
          <select
            value={portfolioId ?? ""}
            onChange={(e) => setSelectedPortfolio(e.target.value)}
            className="w-full sm:w-auto max-w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--foreground)] min-h-11"
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.strategy})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Summary KPI strip */}
      <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 sm:divide-x sm:divide-y-0 divide-y divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Market Value
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
            {isLoading ? "—" : summary ? fmt(summary.total_market_value) : "—"}
          </dd>
        </div>
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Cost Basis
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
            {isLoading ? "—" : summary ? fmt(summary.total_cost_basis) : "—"}
          </dd>
        </div>
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Unrealized P&L
          </dt>
          <dd
            className={`mt-1 text-2xl font-semibold ${
              summary && Number(summary.total_unrealized_pnl) >= 0
                ? "text-[var(--success)]"
                : "text-[var(--destructive)]"
            }`}
          >
            {isLoading ? "—" : summary ? fmt(summary.total_unrealized_pnl) : "—"}
          </dd>
        </div>
        <div className="p-5">
          <dt className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Positions
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-[var(--foreground-bright)]">
            {isLoading ? "—" : summary ? summary.position_count : "—"}
          </dd>
        </div>
      </dl>

      {/* Positions table */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-x-auto">
        <table className="w-full text-sm min-w-[780px]">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Instrument
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Quantity
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Avg Cost
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Market Price
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Market Value
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Unrealized P&L
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                Ccy
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8">
                  <TableSkeleton rows={5} columns={7} />
                </td>
              </tr>
            ) : !positions || positions.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                >
                  No positions found.
                </td>
              </tr>
            ) : (
              positions.map((pos) => {
                const pnl = Number(pos.unrealized_pnl);
                return (
                  <tr
                    key={pos.instrument_id}
                    className="hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-4 py-3 font-medium text-[var(--foreground)]">
                      {pos.instrument_id}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {Number(pos.quantity).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fmt(pos.avg_cost)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fmt(pos.market_price)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fmt(pos.market_value)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular-nums font-medium ${
                        pnl >= 0
                          ? "text-[var(--success)]"
                          : "text-[var(--destructive)]"
                      }`}
                    >
                      {fmt(pos.unrealized_pnl)}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">
                      {pos.currency}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Documents Tab
   ═══════════════════════════════════════════════════════════════════ */

function DocumentsTab({ slug }: { slug: string }) {
  const {
    data: statements,
    isLoading: stmtLoading,
    error: stmtError,
  } = useQuery({
    queryKey: ["investor-statements", slug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/regulatory/investor-statements", {
        headers: fundHeaders(slug),
      });
      if (error) throw error;
      return data;
    },
  });

  const {
    data: letters,
    isLoading: letLoading,
    error: letError,
  } = useQuery({
    queryKey: ["performance-letters", slug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/regulatory/performance-letters", {
        headers: fundHeaders(slug),
      });
      if (error) throw error;
      return data;
    },
  });

  const error = stmtError || letError;
  if (error) return <ErrorState message={String(error)} />;

  const isLoading = stmtLoading || letLoading;

  return (
    <div className="space-y-8">
      {/* Investor Statements */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-[var(--foreground-bright)]">
          Investor Statements
        </h2>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Investor
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Period
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Beginning Capital
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Ending Capital
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Net Return %
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Generated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8">
                    <TableSkeleton rows={4} columns={6} />
                  </td>
                </tr>
              ) : !statements || statements.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    No investor statements available.
                  </td>
                </tr>
              ) : (
                statements.map((s, i) => (
                  <tr
                    key={`${s.investor_id}-${s.period_start}-${i}`}
                    className="hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-4 py-3 font-medium text-[var(--foreground)]">
                      {s.investor_name}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">
                      {fmtDate(s.period_start)} &ndash; {fmtDate(s.period_end)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fmt(s.beginning_capital)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium">
                      {fmt(s.ending_capital)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular-nums ${
                        Number(s.net_return_pct) >= 0
                          ? "text-[var(--success)]"
                          : "text-[var(--destructive)]"
                      }`}
                    >
                      {pct(s.net_return_pct)}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">
                      {fmtDate(s.generated_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Performance Letters */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-[var(--foreground-bright)]">
          Performance Letters
        </h2>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--table-header)]">
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Period
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Fund NAV
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Fund Return %
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Benchmark %
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Alpha %
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                  Generated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--table-border)]">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8">
                    <TableSkeleton rows={4} columns={6} />
                  </td>
                </tr>
              ) : !letters || letters.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    No performance letters available.
                  </td>
                </tr>
              ) : (
                letters.map((l, i) => (
                  <tr
                    key={`${l.fund_slug}-${l.period}-${i}`}
                    className="hover:bg-[var(--table-row-hover)]"
                  >
                    <td className="px-4 py-3 font-medium text-[var(--foreground)]">
                      {l.period}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fmt(l.total_aum)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular-nums ${
                        Number(l.net_return_pct) >= 0
                          ? "text-[var(--success)]"
                          : "text-[var(--destructive)]"
                      }`}
                    >
                      {pct(l.net_return_pct)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {pct(l.benchmark_return_pct)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular-nums ${
                        Number(l.active_return_pct) >= 0
                          ? "text-[var(--success)]"
                          : "text-[var(--destructive)]"
                      }`}
                    >
                      {pct(l.active_return_pct)}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted-foreground)]">
                      {fmtDate(l.generated_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
