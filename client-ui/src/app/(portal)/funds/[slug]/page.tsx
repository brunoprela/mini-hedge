"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api";
import { ErrorState } from "@/shared/components/error-state";
import type {
  PortfolioInfo,
  PortfolioSummary,
  Position,
  FundCapitalOverview,
  InvestorStatement,
  MonthlyPerformanceLetter,
} from "@/shared/types";

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
      <div>
        <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">
          Fund Detail
        </h1>
        <p className="text-sm text-[var(--muted-foreground)]">{slug}</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg border border-[var(--border)] bg-[var(--muted)] p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
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
    queryFn: () =>
      apiFetch<NavRow[]>(`eod/nav/history?fund_slug=${slug}&period=90d`),
  });

  const {
    data: overview,
    isLoading: ovLoading,
    error: ovError,
  } = useQuery({
    queryKey: ["capital-overview", slug],
    queryFn: () =>
      apiFetch<FundCapitalOverview>(`funds/${slug}/capital/overview`),
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
      <dl className="grid grid-cols-4 divide-x divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)]">
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
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
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
                <td
                  colSpan={4}
                  className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                >
                  Loading...
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
    queryFn: () =>
      apiFetch<PortfolioInfo[]>(`portfolios?fund_slug=${slug}`),
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
    queryFn: () =>
      apiFetch<PortfolioSummary>(`portfolios/${portfolioId}/summary`),
    enabled: !!portfolioId,
  });

  const {
    data: positions,
    isLoading: posLoading,
    error: posError,
  } = useQuery({
    queryKey: ["portfolio-positions", portfolioId],
    queryFn: () =>
      apiFetch<Position[]>(`portfolios/${portfolioId}/positions`),
    enabled: !!portfolioId,
  });

  const error = portError || sumError || posError;
  if (error) return <ErrorState message={String(error)} />;

  const isLoading = portLoading || sumLoading || posLoading;

  return (
    <div className="space-y-6">
      {/* Portfolio selector */}
      {portfolios && portfolios.length > 1 && (
        <div>
          <label className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide mr-2">
            Portfolio
          </label>
          <select
            value={portfolioId ?? ""}
            onChange={(e) => setSelectedPortfolio(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--foreground)]"
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
      <dl className="grid grid-cols-4 divide-x divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)]">
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
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <table className="w-full text-sm">
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
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                >
                  Loading...
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
    queryFn: () =>
      apiFetch<InvestorStatement[]>(
        `funds/${slug}/regulatory/investor-statements`,
      ),
  });

  const {
    data: letters,
    isLoading: letLoading,
    error: letError,
  } = useQuery({
    queryKey: ["performance-letters", slug],
    queryFn: () =>
      apiFetch<MonthlyPerformanceLetter[]>(
        `funds/${slug}/regulatory/performance-letters`,
      ),
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
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
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
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    Loading...
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
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <table className="w-full text-sm">
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
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--muted-foreground)]"
                  >
                    Loading...
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
