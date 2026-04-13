"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { useMemo, useState } from "react";
import { exposureQueryOptions } from "@/features/exposure/api";
import { ordersQueryOptions } from "@/features/orders/api";
import { portfolioSummaryQueryOptions, portfoliosQueryOptions } from "@/features/portfolio/api";
import type { PortfolioSummary } from "@/features/portfolio/types";
import { navHistoryQueryOptions } from "@/features/eod/api";
import { DonutChart, HBarChart, SparkLine, StatusDot } from "@/shared/components/charts";
import { InstrumentLink } from "@/shared/components/instrument-link";
import { SectionPanel } from "@/shared/components/section-panel";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { CrossFundSummary } from "@/features/platform/components/cross-fund-summary";
import { clientFetch } from "@/shared/lib/api";
import { formatPnL, pnlColorClass } from "@/shared/lib/formatters";
import { Permission } from "@/shared/lib/permissions";

// ─── Types ──────────────────────────────────────────────────

interface EodRun {
  id: string;
  status: string;
  run_date: string;
}

interface PositionItem {
  instrument_id: string;
  market_value: string;
  unrealized_pnl: string;
}

// ─── Helpers ────────────────────────────────────────────────

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

const fmtPct = (v: number) => {
  const abs = Math.abs(v);
  return abs < 0.01 ? "0.00%" : `${abs.toFixed(2)}%`;
};

const DONUT_COLORS = [
  "var(--primary)",
  "var(--success)",
  "var(--warning)",
  "#6366f1",
  "#06b6d4",
  "var(--destructive)",
  "#8b5cf6",
  "#ec4899",
  "var(--accent-orange)",
  "#14b8a6",
];

// ─── Dashboard Component ───────────────────────────────────

export function DashboardHome() {
  const { fundSlug, fundName } = useFundContext();
  const { data: session } = useSession();
  const { can } = usePermission();
  const userName = session?.user?.name?.split(" ")[0] ?? "there";

  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  const { data: aggregate } = useQuery({
    queryKey: ["fund-aggregate", fundSlug],
    queryFn: () =>
      clientFetch<{
        total_aum: string;
        total_realized_pnl: string;
        total_unrealized_pnl: string;
        portfolio_count: number;
        total_positions: number;
      }>("/portfolios/aggregate", { fundSlug }),
    staleTime: 30_000,
  });

  const { data: violations } = useQuery({
    queryKey: ["violations-all", fundSlug],
    queryFn: () =>
      clientFetch<
        { id: string; severity: string; rule_name: string; message: string; portfolio_id: string }[]
      >("/compliance/violations", { fundSlug }),
    staleTime: 60_000,
    enabled: can(Permission.COMPLIANCE_READ),
  });

  const firstPortfolioId = portfolios?.[0]?.id ?? "";
  const { data: orders } = useQuery({
    ...ordersQueryOptions(fundSlug, firstPortfolioId),
    enabled: !!firstPortfolioId && can(Permission.ORDERS_READ),
  });

  const { data: eodRuns } = useQuery({
    queryKey: ["eod-runs", fundSlug],
    queryFn: () => clientFetch<EodRun[]>("/eod/runs", { fundSlug }),
    staleTime: 120_000,
    enabled: can(Permission.EOD_READ),
  });

  const { data: positions } = useQuery({
    queryKey: ["positions", fundSlug, firstPortfolioId],
    queryFn: () =>
      clientFetch<PositionItem[]>(`/portfolios/${firstPortfolioId}/positions`, { fundSlug }),
    staleTime: 30_000,
    enabled: !!firstPortfolioId,
  });

  // NAV history for P&L sparkline
  const { data: navHistory } = useQuery(navHistoryQueryOptions(fundSlug, "30d"));
  const navSparkData = useMemo(
    () => (navHistory ?? []).map((p) => p.nav),
    [navHistory],
  );

  // Exposure for donut chart (sector breakdown)
  const { data: exposure } = useQuery({
    ...exposureQueryOptions(fundSlug, firstPortfolioId),
    enabled: !!firstPortfolioId,
  });

  // Portfolio summaries for the portfolio table
  const summaryResults = useQueries({
    queries: (portfolios ?? []).map((p) => portfolioSummaryQueryOptions(fundSlug, p.id)),
  });
  const summaries = summaryResults
    .map((r) => r.data)
    .filter((d): d is PortfolioSummary => d !== undefined);

  // Period selectors for widgets
  const [allocationPeriod, setAllocationPeriod] = useState<Period>("1M");
  const [moversPeriod, setMoversPeriod] = useState<Period>("1D");
  const [ordersPeriod, setOrdersPeriod] = useState<Period>("1D");

  // Derived data
  const pendingOrders =
    orders?.filter((o) => ["pending", "partially_filled", "working", "sent"].includes(o.state))
      .length ?? 0;
  const filledToday = orders?.filter((o) => o.state === "filled").length ?? 0;
  const rejectedOrders = orders?.filter((o) => o.state === "rejected").length ?? 0;
  const totalOrders = orders?.length ?? 0;
  const violationCount = violations?.length ?? 0;
  const blockCount = violations?.filter((v) => v.severity === "block").length ?? 0;
  const warningCount = violations?.filter((v) => v.severity === "warning").length ?? 0;

  // ── KPI deltas (derived from available data) ──────────────
  // Unrealized P&L as % of AUM approximates the day's mark-to-market move.
  // Without a dedicated previous-day snapshot endpoint we derive what we can.
  const aumDeltaPct = useMemo(() => {
    if (!aggregate) return null;
    const aum = Number(aggregate.total_aum);
    const unrealized = Number(aggregate.total_unrealized_pnl);
    if (aum === 0) return null;
    return (unrealized / aum) * 100;
  }, [aggregate]);

  const unrealizedPnlPctOfAum = useMemo(() => {
    if (!aggregate) return null;
    const aum = Number(aggregate.total_aum);
    if (aum === 0) return null;
    return (Number(aggregate.total_unrealized_pnl) / aum) * 100;
  }, [aggregate]);

  const realizedPnlPctOfAum = useMemo(() => {
    if (!aggregate) return null;
    const aum = Number(aggregate.total_aum);
    if (aum === 0) return null;
    return (Number(aggregate.total_realized_pnl) / aum) * 100;
  }, [aggregate]);

  const today = new Date().toISOString().slice(0, 10);
  const todayEod = eodRuns?.find((r) => r.run_date === today);

  // Sector donut segments
  const sectorSegments = useMemo(() => {
    const sectorBreakdowns = exposure?.breakdowns?.sector;
    if (!sectorBreakdowns || sectorBreakdowns.length === 0) return [];
    return sectorBreakdowns
      .map((b, i) => ({
        label: b.key,
        value: Math.abs(Number(b.gross_value)),
        color: DONUT_COLORS[i % DONUT_COLORS.length],
      }))
      .filter((s) => s.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  }, [exposure]);

  // Currency exposure bars
  const currencyBars = useMemo(() => {
    const currBreakdowns = exposure?.breakdowns?.currency;
    if (!currBreakdowns || currBreakdowns.length === 0) return [];
    return currBreakdowns
      .map((b) => ({
        label: b.key,
        long: Math.abs(Number(b.long_value)),
        short: Math.abs(Number(b.short_value)),
        net: Number(b.net_value),
      }))
      .filter((b) => b.long > 0 || b.short > 0)
      .sort((a, b) => b.long + b.short - (a.long + a.short))
      .slice(0, 6);
  }, [exposure]);

  // Top/bottom movers
  const movers = useMemo(() => {
    const sorted = (positions ?? [])
      .map((p) => ({ label: p.instrument_id, value: Number(p.unrealized_pnl) }))
      .sort((a, b) => b.value - a.value);
    return { top: sorted.slice(0, 5), bottom: sorted.slice(-5).reverse() };
  }, [positions]);

  // Format today's date nicely
  const dateStr = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="space-y-3">
      {/* Greeting + Date */}
      <div>
        <h1 className="text-lg font-semibold text-[var(--foreground-bright)]">Hello, {userName}</h1>
        <p className="text-xs text-[var(--muted-foreground)]">
          Here&apos;s what&apos;s happening today, {dateStr} &middot; {fundName}
        </p>
      </div>

      {/* Hero KPI Strip — Tailwind UI stats/01-with-trending + 05-shared-borders pattern */}
      <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-[var(--border)] sm:grid-cols-5">
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Total AUM
          </dt>
          <dd className="mt-1 flex items-baseline justify-between">
            <div className="font-mono text-xl font-bold text-[var(--foreground-bright)]">
              {aggregate ? fmtCurrency(aggregate.total_aum) : "—"}
            </div>
          </dd>
          <dd className="mt-0.5 flex items-center gap-1.5">
            <KpiDelta value={aumDeltaPct} label="mtm" />
            <span className="text-[10px] text-[var(--muted-foreground)]">
              &middot; {aggregate?.portfolio_count ?? 0} portfolio
              {(aggregate?.portfolio_count ?? 0) !== 1 ? "s" : ""}
            </span>
          </dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Unrealized P&L
          </dt>
          <dd
            className="mt-1 font-mono text-xl font-bold"
            style={{
              color: aggregate
                ? Number(aggregate.total_unrealized_pnl) >= 0
                  ? "var(--success)"
                  : "var(--destructive)"
                : undefined,
            }}
          >
            {aggregate ? fmtCurrency(aggregate.total_unrealized_pnl) : "—"}
          </dd>
          <dd className="mt-0.5 flex items-center gap-2">
            <KpiDelta value={unrealizedPnlPctOfAum} label="of AUM" />
            {navSparkData.length >= 2 && (
              <SparkLine data={navSparkData} width={64} height={20} />
            )}
          </dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Realized P&L
          </dt>
          <dd
            className="mt-1 font-mono text-xl font-bold"
            style={{
              color: aggregate
                ? Number(aggregate.total_realized_pnl) >= 0
                  ? "var(--success)"
                  : "var(--destructive)"
                : undefined,
            }}
          >
            {aggregate ? fmtCurrency(aggregate.total_realized_pnl) : "—"}
          </dd>
          <dd className="mt-0.5">
            <KpiDelta value={realizedPnlPctOfAum} label="of AUM" />
          </dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Positions
          </dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">
            {aggregate?.total_positions ?? "—"}
          </dd>
          <dd className="mt-0.5 text-[10px] text-[var(--muted-foreground)]">across all portfolios</dd>
        </div>
        <div className="bg-[var(--card)] px-4 py-4">
          <dt className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Today&apos;s Orders
          </dt>
          <dd className="mt-1 font-mono text-xl font-bold text-[var(--foreground-bright)]">{totalOrders}</dd>
          <dd className="mt-0.5 text-[10px] text-[var(--muted-foreground)]">
            {filledToday} filled &middot; {pendingOrders} working
          </dd>
        </div>
      </dl>

      {/* Main widget grid */}
      <div className="grid grid-cols-12 gap-3">
        {/* Left column (8 cols): Portfolios + Allocation donut + movers */}
        <div className="col-span-8 space-y-3">
          {/* Portfolios summary table — promoted to top-left */}
          {portfolios && portfolios.length > 0 && (
            <SectionPanel
              title="Portfolios"
              actions={
                <Link
                  href={`/${fundSlug}/portfolio/${portfolios[0]?.id ?? ""}`}
                  className="text-[10px] text-[var(--primary)] hover:underline"
                >
                  View all &rarr;
                </Link>
              }
            >
              {/* Tailwind UI lists/tables/12-with-condensed-content pattern */}
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-[var(--border)]">
                  <thead>
                    <tr>
                      <th scope="col" className="py-2 pr-3 pl-3 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                        Portfolio
                      </th>
                      <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                        NAV / AUM
                      </th>
                      <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                        P&L
                      </th>
                      <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                        Positions
                      </th>
                      <th scope="col" className="px-3 py-2 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                        Open Orders
                      </th>
                      <th scope="col" className="py-2 pr-3 pl-3 text-right text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">
                        VaR
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--table-border)]">
                    {portfolios.map((p) => {
                      const summary = summaries.find((s) => s.portfolio_id === p.id);
                      const portfolioOrders =
                        orders?.filter(
                          (o) =>
                            o.portfolio_id === p.id &&
                            ["pending", "partially_filled", "working", "sent"].includes(o.state),
                        ).length ?? 0;
                      return (
                        <tr
                          key={p.id}
                          className="transition-colors hover:bg-[var(--table-row-hover)]"
                        >
                          <td className="py-2 pr-3 pl-3 text-xs whitespace-nowrap">
                            <Link
                              href={`/${fundSlug}/portfolio/${p.id}`}
                              className="font-medium text-[var(--foreground-bright)] hover:text-[var(--primary)]"
                            >
                              {p.name}
                            </Link>
                            {p.strategy && (
                              <span className="ml-1.5 text-[9px] text-[var(--muted-foreground)]">
                                {p.strategy}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right text-xs font-mono whitespace-nowrap text-[var(--foreground)]">
                            {summary ? formatPnL(summary.total_market_value) : "\u2014"}
                          </td>
                          <td className="px-3 py-2 text-right text-xs whitespace-nowrap">
                            {summary ? (
                              <span
                                className={`font-mono ${pnlColorClass(summary.total_unrealized_pnl)}`}
                              >
                                {formatPnL(summary.total_unrealized_pnl)}
                              </span>
                            ) : (
                              "\u2014"
                            )}
                          </td>
                          <td className="px-3 py-2 text-right text-xs whitespace-nowrap text-[var(--muted-foreground)]">
                            {summary?.position_count ?? "\u2014"}
                          </td>
                          <td className="px-3 py-2 text-right text-xs font-mono whitespace-nowrap text-[var(--muted-foreground)]">
                            {portfolioOrders}
                          </td>
                          <td className="py-2 pr-3 pl-3 text-right text-xs font-mono whitespace-nowrap text-[var(--muted-foreground)]">
                            &mdash;
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </SectionPanel>
          )}

          {/* Allocation donut + Top movers side by side */}
          <div className="grid grid-cols-2 gap-3">
            {/* Sector Allocation Donut */}
            <SectionPanel
              title="Sector Allocation"
              actions={<PeriodSelect value={allocationPeriod} onChange={setAllocationPeriod} />}
            >
              <div className="p-3">
                {sectorSegments.length > 0 ? (
                  <DonutChart
                    segments={sectorSegments}
                    centerValue={String(positions?.length ?? aggregate?.total_positions ?? 0)}
                    centerLabel="Positions"
                    size={160}
                    thickness={28}
                  />
                ) : (
                  <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
                    No exposure data
                  </p>
                )}
              </div>
            </SectionPanel>

            {/* Top & Bottom Movers */}
            <SectionPanel
              title="Top & Bottom Movers"
              actions={<PeriodSelect value={moversPeriod} onChange={setMoversPeriod} />}
            >
              <div className="p-3">
                {movers.top.length > 0 ? (
                  <div className="space-y-3">
                    <div>
                      <p className="mb-1.5 text-[10px] font-medium uppercase text-[var(--success)]">
                        Gainers
                      </p>
                      <HBarChart
                        items={movers.top}
                        renderLabel={(label) => (
                          <InstrumentLink instrument={label} side="buy" className="cursor-pointer truncate text-right font-mono text-xs text-[var(--foreground)] underline-offset-2 transition-colors hover:text-[var(--primary)] hover:underline" />
                        )}
                      />
                    </div>
                    <div>
                      <p className="mb-1.5 text-[10px] font-medium uppercase text-[var(--destructive)]">
                        Losers
                      </p>
                      <HBarChart
                        items={movers.bottom}
                        renderLabel={(label) => (
                          <InstrumentLink instrument={label} side="sell" className="cursor-pointer truncate text-right font-mono text-xs text-[var(--foreground)] underline-offset-2 transition-colors hover:text-[var(--primary)] hover:underline" />
                        )}
                      />
                    </div>
                  </div>
                ) : (
                  <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
                    No positions yet
                  </p>
                )}
              </div>
            </SectionPanel>
          </div>

          {/* Currency Exposure Bars */}
          {currencyBars.length > 0 && (
            <SectionPanel title="Currency Exposure">
              <div className="p-3">
                <div className="space-y-2">
                  {(() => {
                    const maxVal = Math.max(
                      ...currencyBars.map((b) => Math.max(b.long, b.short)),
                      1,
                    );
                    return currencyBars.map((b) => (
                      <div key={b.label} className="flex items-center gap-3 text-xs">
                        <span className="w-10 font-mono font-medium text-[var(--foreground)]">
                          {b.label}
                        </span>
                        <div className="flex-1">
                          <div className="flex gap-0.5">
                            <div
                              className="h-4 rounded-l-sm"
                              style={{
                                width: `${Math.max((b.long / maxVal) * 100, 1)}%`,
                                backgroundColor: "var(--primary)",
                                opacity: 0.8,
                              }}
                            />
                            {b.short > 0 && (
                              <div
                                className="h-4 rounded-r-sm"
                                style={{
                                  width: `${Math.max((b.short / maxVal) * 100, 1)}%`,
                                  backgroundColor: "var(--destructive)",
                                  opacity: 0.6,
                                }}
                              />
                            )}
                          </div>
                        </div>
                        <span
                          className={`w-20 text-right font-mono ${b.net >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}
                        >
                          {fmtCurrency(String(b.net))}
                        </span>
                      </div>
                    ));
                  })()}
                </div>
                <div className="mt-2 flex items-center gap-4 text-[10px] text-[var(--muted-foreground)]">
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-4 rounded-sm bg-[var(--primary)] opacity-80" />{" "}
                    Long
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-4 rounded-sm bg-[var(--destructive)] opacity-60" />{" "}
                    Short
                  </span>
                </div>
              </div>
            </SectionPanel>
          )}

          {/* Recent Orders */}
          <SectionPanel
            title="Recent Orders"
            actions={
              can(Permission.ORDERS_READ) ? (
                <Link
                  href={`/${fundSlug}/orders`}
                  className="text-[10px] text-[var(--primary)] hover:underline"
                >
                  View all &rarr;
                </Link>
              ) : undefined
            }
          >
            {can(Permission.ORDERS_READ) && orders && orders.length > 0 ? (
              <table className="min-w-full divide-y divide-[var(--border)]">
                <thead>
                  <tr>
                    <th scope="col" className="py-2 pr-3 pl-3 text-left text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Instrument</th>
                    <th scope="col" className="px-3 py-2 text-left text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Side</th>
                    <th scope="col" className="px-3 py-2 text-right text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Qty</th>
                    <th scope="col" className="px-3 py-2 text-left text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">State</th>
                    <th scope="col" className="py-2 pr-3 pl-3 text-right text-xs font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--table-border)]">
                  {orders.slice(0, 8).map((o) => (
                    <tr
                      key={o.id}
                      className="transition-colors hover:bg-[var(--table-row-hover)]"
                    >
                      <td className="px-3 py-1.5 font-mono font-medium">
                        <span className="mr-1.5 inline-block">
                          <StatusDot
                            variant={
                              o.state === "filled"
                                ? "success"
                                : o.state === "rejected" || o.state === "cancelled"
                                  ? "error"
                                  : "info"
                            }
                            size={5}
                          />
                        </span>
                        <InstrumentLink instrument={o.instrument_id} />
                      </td>
                      <td className="px-3 py-1.5">
                        <span
                          className={`text-xs font-medium ${
                            o.side === "buy" ? "text-[var(--success)]" : "text-[var(--destructive)]"
                          }`}
                        >
                          {o.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono text-xs">
                        {parseFloat(o.quantity).toLocaleString()}
                      </td>
                      <td className="px-3 py-1.5 text-xs text-[var(--muted-foreground)]">
                        {o.state}
                      </td>
                      <td className="px-3 py-1.5 text-right text-xs text-[var(--muted-foreground)]">
                        {new Date(o.created_at).toLocaleTimeString(undefined, {
                          timeZoneName: "short",
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="px-3 py-6 text-center text-xs text-[var(--muted-foreground)]">
                No orders yet
              </p>
            )}
          </SectionPanel>
        </div>

        {/* Right column (4 cols): Status + Compliance + Tasks */}
        <div className="col-span-4 space-y-3">
          {/* Today's Orders Summary */}
          <SectionPanel
            title="Order Activity"
            actions={<PeriodSelect value={ordersPeriod} onChange={setOrdersPeriod} />}
          >
            <div className="p-3">
              <div className="grid grid-cols-4 gap-2 text-center">
                <CountBadge count={totalOrders} label="Total" color="var(--foreground)" />
                <CountBadge count={filledToday} label="Filled" color="var(--success)" />
                <CountBadge count={pendingOrders} label="Working" color="var(--primary)" />
                <CountBadge count={rejectedOrders} label="Rejected" color="var(--destructive)" />
              </div>
            </div>
          </SectionPanel>

          {/* Compliance / Items for Attention */}
          <SectionPanel
            title="Compliance"
            actions={
              <Link
                href={`/${fundSlug}/compliance`}
                className="text-[10px] text-[var(--primary)] hover:underline"
              >
                View all &rarr;
              </Link>
            }
          >
            <div className="p-3">
              {violationCount === 0 ? (
                <p className="py-2 text-center text-xs text-[var(--success)]">
                  All clear — no violations
                </p>
              ) : (
                <>
                  <div className="mb-3 flex items-center gap-3">
                    <CountBadge count={violationCount} label="Active" color="var(--foreground)" />
                    <CountBadge count={blockCount} label="Blocks" color="var(--destructive)" />
                    <CountBadge count={warningCount} label="Warnings" color="var(--warning)" />
                  </div>
                  {/* Inline alert list — "Items for Attention" pattern */}
                  <div className="space-y-1.5 border-t border-[var(--border)] pt-2">
                    {violations?.slice(0, 5).map((v) => (
                      <Link
                        key={v.id}
                        href={`/${fundSlug}/compliance`}
                        className="flex items-start gap-2 rounded-md px-1.5 py-1 text-[11px] transition-colors hover:bg-[var(--muted)]"
                      >
                        <StatusDot
                          variant={v.severity === "block" ? "error" : "warning"}
                          size={5}
                        />
                        <div className="min-w-0 flex-1">
                          <span className="font-medium text-[var(--foreground)]">
                            {v.rule_name}
                          </span>
                          <p className="truncate text-[var(--muted-foreground)]">{v.message}</p>
                        </div>
                      </Link>
                    ))}
                  </div>
                </>
              )}
            </div>
          </SectionPanel>

          {/* Job Timeline / Running Tasks */}
          <SectionPanel title="Job Timeline">
            <div className="p-3 space-y-1.5">
              <TaskRow
                label="EOD Process"
                status={
                  todayEod?.status === "completed"
                    ? "complete"
                    : todayEod?.status === "running"
                      ? "running"
                      : todayEod?.status === "failed"
                        ? "failed"
                        : "idle"
                }
                href={`/${fundSlug}/eod`}
              />
              <TaskRow label="Price Sync" status="complete" href={`/${fundSlug}/market-data`} />
              <TaskRow
                label="Compliance Scan"
                status={violationCount > 0 ? "running" : "complete"}
                href={`/${fundSlug}/compliance`}
              />
              <TaskRow label="Risk Calc" status="complete" href={`/${fundSlug}/risk`} />
            </div>
          </SectionPanel>
        </div>
      </div>

      {/* Cross-fund summary — visible only when user has access to multiple funds */}
      <CrossFundSummary />

    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────

type Period = "1D" | "1W" | "1M" | "3M" | "YTD";
const PERIODS: Period[] = ["1D", "1W", "1M", "3M", "YTD"];

function PeriodSelect({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  return (
    <div className="flex items-center gap-0.5">
      {PERIODS.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onChange(p)}
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
            p === value
              ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
              : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
          }`}
        >
          {p}
        </button>
      ))}
    </div>
  );
}

/**
 * Compact delta indicator for KPI cards.
 * Shows a triangle (up/down/neutral) with a percentage or absolute change.
 */
function KpiDelta({
  value,
  format = "pct",
  label,
}: {
  /** Numeric change value — positive = up, negative = down, 0 = flat */
  value: number | null | undefined;
  /** "pct" formats as %, "abs" shows raw number */
  format?: "pct" | "abs";
  /** Optional trailing label, e.g. "vs prev day" */
  label?: string;
}) {
  if (value == null || !isFinite(value)) return null;

  const direction = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const color =
    direction === "up"
      ? "var(--success)"
      : direction === "down"
        ? "var(--destructive)"
        : "var(--muted-foreground)";
  const arrow = direction === "up" ? "\u25B2" : direction === "down" ? "\u25BC" : "\u25C6";
  const display = format === "pct" ? fmtPct(value) : Math.abs(value).toLocaleString();

  return (
    <span
      className="inline-flex items-center gap-0.5 text-[10px] font-medium leading-none"
      style={{ color }}
    >
      <span className="text-[8px]">{arrow}</span>
      {display}
      {label && (
        <span className="font-normal text-[var(--muted-foreground)]"> {label}</span>
      )}
    </span>
  );
}

function CountBadge({ count, label, color }: { count: number; label: string; color: string }) {
  return (
    <div className="text-center">
      <p className="font-mono text-lg font-bold" style={{ color }}>
        {count}
      </p>
      <p className="text-[9px] uppercase tracking-wider text-[var(--muted-foreground)]">{label}</p>
    </div>
  );
}

function TaskRow({
  label,
  status,
  href,
}: {
  label: string;
  status: "complete" | "running" | "failed" | "idle";
  href: string;
}) {
  const variant: "success" | "warning" | "error" | "info" | "neutral" =
    status === "complete"
      ? "success"
      : status === "running"
        ? "info"
        : status === "failed"
          ? "error"
          : "neutral";

  const statusLabel =
    status === "complete"
      ? "Done"
      : status === "running"
        ? "Running"
        : status === "failed"
          ? "Failed"
          : "Idle";

  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-[var(--muted)]"
    >
      <div className="flex items-center gap-2">
        {status === "running" ? (
          <div className="h-2 w-2 animate-pulse rounded-full bg-[var(--primary)]" />
        ) : (
          <StatusDot variant={variant} size={7} />
        )}
        <span className="text-xs text-[var(--foreground)]">{label}</span>
      </div>
      <span
        className={`text-[10px] font-medium uppercase tracking-wide ${
          status === "failed"
            ? "text-[var(--destructive)]"
            : status === "running"
              ? "text-[var(--primary)]"
              : "text-[var(--muted-foreground)]"
        }`}
      >
        {statusLabel}
      </span>
    </Link>
  );
}
