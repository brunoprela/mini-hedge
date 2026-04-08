"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { AttributionSummaryCard } from "@/features/attribution/components/attribution-summary-card";
import { cumulativeQueryOptions } from "@/features/attribution/api";
import { CashSummaryCard } from "@/features/cash/components/cash-summary-card";
import { ComplianceBanner } from "@/features/compliance/components/compliance-banner";
import { ExposureHistoryChart } from "@/features/exposure/components/exposure-history-chart";
import { ExposureSummary } from "@/features/exposure/components/exposure-summary";
import { ForwardsTable, FXSummaryCards } from "@/features/fx-hedging";
import { OrderBlotter } from "@/features/orders/components/order-blotter";
import { positionsQueryOptions, portfolioSummaryQueryOptions } from "@/features/portfolio/api";
import { PositionTable } from "@/features/portfolio/components/position-table";
import { RiskHistoryChart } from "@/features/risk/components/risk-history-chart";
import { RiskSummaryCard } from "@/features/risk/components/risk-summary-card";
import { riskSnapshotQueryOptions } from "@/features/risk/api";
import { StressTable } from "@/features/risk/components/stress-table";
import { CustomStressForm } from "@/features/risk/components/custom-stress-form";
import { TCADashboard } from "@/features/tca/components/tca-dashboard";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { cn } from "@/shared/lib/cn";
import { LineChart, HBarChart, GaugeBar, SummaryStrip, DonutChart } from "@/shared/components/charts";
import { exposureQueryOptions } from "@/features/exposure/api";
import { SectionPanel } from "@/shared/components/section-panel";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "positions", label: "Positions" },
  { id: "orders", label: "Orders" },
  { id: "risk", label: "Risk & Exposure" },
  { id: "cash", label: "Cash & FX" },
  { id: "attribution", label: "Attribution" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

// ─── Main Component ─────────────────────────────────────────

export function PortfolioDetailClient({ portfolioId }: { portfolioId: string }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { fundSlug } = useFundContext();
  const initialTab = (searchParams.get("tab") as TabId) || "overview";
  const [activeTab, setActiveTab] = useState<TabId>(
    TABS.some((t) => t.id === initialTab) ? initialTab : "overview",
  );

  function switchTab(tab: TabId) {
    setActiveTab(tab);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    router.replace(url.pathname + url.search, { scroll: false });
  }

  return (
    <div className="space-y-3">
      <ComplianceBanner portfolioId={portfolioId} />

      {/* Sticky header: title + actions + tabs */}
      <div className="sticky top-0 z-10 -mx-6 border-b border-[var(--border)] bg-[var(--background)] px-6 pb-0 pt-2">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="text-sm font-semibold">Portfolio</h1>
          <ActionBar portfolioId={portfolioId} fundSlug={fundSlug} onSwitchTab={switchTab} />
        </div>
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => switchTab(tab.id)}
              className={cn(
                "rounded-t-lg px-3 py-1.5 text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="pt-2">
        {activeTab === "overview" && <OverviewTab portfolioId={portfolioId} />}
        {activeTab === "positions" && <PositionsTab portfolioId={portfolioId} />}
        {activeTab === "orders" && <OrdersTab portfolioId={portfolioId} />}
        {activeTab === "risk" && <RiskTab portfolioId={portfolioId} />}
        {activeTab === "cash" && <CashTab portfolioId={portfolioId} />}
        {activeTab === "attribution" && <AttributionTab portfolioId={portfolioId} />}
      </div>
    </div>
  );
}

// ─── Action Bar ─────────────────────────────────────────────

function ActionBar({
  portfolioId,
  fundSlug,
  onSwitchTab,
}: {
  portfolioId: string;
  fundSlug: string;
  onSwitchTab: (tab: TabId) => void;
}) {
  const { can } = usePermission();
  const searchParams = useSearchParams();
  const [showTradeTicket, setShowTradeTicket] = useState(false);
  const [tradeDefaults, setTradeDefaults] = useState<{
    instrument?: string;
    side?: string;
    quantity?: string;
  }>({});

  useEffect(() => {
    const instrument = searchParams.get("trade_instrument");
    const side = searchParams.get("trade_side");
    const qty = searchParams.get("trade_qty");
    if (instrument) {
      setTradeDefaults({ instrument, side: side || undefined, quantity: qty || undefined });
      setShowTradeTicket(true);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex items-center gap-2">
      {can("trades:execute") && (
        <button
          type="button"
          onClick={() => {
            setTradeDefaults({});
            setShowTradeTicket(true);
          }}
          className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:opacity-90"
        >
          New Trade
        </button>
      )}
      <button
        type="button"
        onClick={() => onSwitchTab("risk")}
        className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
      >
        Run Stress Test
      </button>
      {showTradeTicket && (
        <TradeTicketLazy
          portfolioId={portfolioId}
          onClose={() => setShowTradeTicket(false)}
          defaults={tradeDefaults}
        />
      )}
    </div>
  );
}

const TradeTicketLazy = dynamic(
  () =>
    import("@/features/portfolio/components/trade-ticket").then((mod) => mod.TradeTicket),
  { ssr: false },
);

// ─── Overview Tab (Broadridge-style) ────────────────────────

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

function OverviewTab({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();

  // Portfolio summary
  const { data: summary } = useQuery(portfolioSummaryQueryOptions(fundSlug, portfolioId));

  // Risk snapshot
  const { data: risk } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

  // Exposure for donut
  const { data: exposure } = useQuery(exposureQueryOptions(fundSlug, portfolioId));

  // Performance data for line chart
  const end = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const start = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  }, []);
  const { data: perfData } = useQuery(cumulativeQueryOptions(fundSlug, portfolioId, start, end));

  // Positions for movers
  const { data: positions } = useQuery(positionsQueryOptions(fundSlug, portfolioId));

  // Performance line chart data
  const perfSeries = useMemo(() => {
    if (!perfData?.periods) return [];
    return [
      {
        label: "Portfolio",
        color: "var(--primary)",
        data: perfData.periods.map((p) => ({
          x: p.period_end,
          y: parseFloat(p.portfolio_return) * 100,
        })),
      },
      {
        label: "Benchmark",
        color: "var(--muted-foreground)",
        dashed: true,
        data: perfData.periods.map((p) => ({
          x: p.period_end,
          y: parseFloat(p.benchmark_return) * 100,
        })),
      },
    ];
  }, [perfData]);

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
      .sort((a, b) => (b.long + b.short) - (a.long + a.short))
      .slice(0, 8);
  }, [exposure]);

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

  // Top/bottom movers
  const movers = useMemo(() => {
    if (!positions) return { top: [], bottom: [] };
    const sorted = positions
      .map((p) => ({ label: p.instrument_id, value: Number(p.unrealized_pnl) }))
      .sort((a, b) => b.value - a.value);
    return { top: sorted.slice(0, 5), bottom: sorted.slice(-5).reverse() };
  }, [positions]);

  // VaR gauge
  const varValue = risk ? Math.abs(Number(risk.var_95_1d)) : 0;
  const varLimit = 200_000;

  return (
    <div className="space-y-3">
      {/* Hero KPI Strip — Broadridge client dashboard style */}
      {summary && (
        <div className="grid grid-cols-4 gap-3">
          <div className="rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Market Value</p>
            <p className="mt-1 font-mono text-xl font-bold">{fmtCurrency(summary.total_market_value)}</p>
          </div>
          <div className="rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Unrealized P&L</p>
            <p
              className="mt-1 font-mono text-xl font-bold"
              style={{ color: Number(summary.total_unrealized_pnl) >= 0 ? "var(--success)" : "var(--destructive)" }}
            >
              {fmtCurrency(summary.total_unrealized_pnl)}
            </p>
          </div>
          <div className="rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Realized P&L</p>
            <p
              className="mt-1 font-mono text-xl font-bold"
              style={{ color: Number(summary.total_realized_pnl) >= 0 ? "var(--success)" : "var(--destructive)" }}
            >
              {fmtCurrency(summary.total_realized_pnl)}
            </p>
          </div>
          <div className="rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">Positions</p>
            <p className="mt-1 font-mono text-xl font-bold">{summary.position_count}</p>
            <p className="mt-0.5 text-[10px] text-[var(--muted-foreground)]">
              Cost Basis: {fmtCurrency(summary.total_cost_basis)}
            </p>
          </div>
        </div>
      )}

      {/* Main grid: Performance + Allocation Donut + Risk */}
      <div className="grid grid-cols-12 gap-3">
        {/* Performance chart */}
        <div className="col-span-5">
          <SectionPanel title="Performance (30d)">
            <div className="p-3">
              {perfSeries.length > 0 ? (
                <LineChart
                  series={perfSeries}
                  height={200}
                  formatY={(v) => `${v.toFixed(1)}%`}
                  xLabelInterval={7}
                />
              ) : (
                <p className="py-8 text-center text-xs text-[var(--muted-foreground)]">
                  No performance data
                </p>
              )}
            </div>
          </SectionPanel>
        </div>

        {/* Sector Allocation Donut */}
        <div className="col-span-4">
          <SectionPanel title="Sector Allocation">
            <div className="p-3">
              {sectorSegments.length > 0 ? (
                <DonutChart
                  segments={sectorSegments}
                  centerValue={String(positions?.length ?? summary?.position_count ?? 0)}
                  centerLabel="Positions"
                  size={150}
                  thickness={26}
                />
              ) : (
                <p className="py-8 text-center text-xs text-[var(--muted-foreground)]">
                  No exposure data
                </p>
              )}
            </div>
          </SectionPanel>
        </div>

        {/* Risk panel */}
        <div className="col-span-3">
          <SectionPanel title="Risk">
            <div className="p-3">
              <GaugeBar
                value={varValue}
                max={varLimit}
                label="VaR 95% (1d) Utilization"
              />
              {risk && (
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-[var(--muted-foreground)]">VaR 95%</p>
                    <p className="font-mono font-medium">{fmtCurrency(risk.var_95_1d)}</p>
                  </div>
                  <div>
                    <p className="text-[var(--muted-foreground)]">VaR 99%</p>
                    <p className="font-mono font-medium">{fmtCurrency(risk.var_99_1d)}</p>
                  </div>
                </div>
              )}
              <div className="mt-3">
                <ExposureSummary portfolioId={portfolioId} />
              </div>
            </div>
          </SectionPanel>
        </div>
      </div>

      {/* Currency Exposure */}
      {currencyBars.length > 0 && (
        <SectionPanel title="Currency Exposure">
          <div className="p-3">
            <div className="space-y-2">
              {(() => {
                const maxVal = Math.max(...currencyBars.map((b) => Math.max(b.long, b.short)), 1);
                return currencyBars.map((b) => (
                  <div key={b.label} className="flex items-center gap-3 text-xs">
                    <span className="w-10 font-mono font-medium text-[var(--foreground)]">{b.label}</span>
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
                    <span className={`w-20 text-right font-mono ${b.net >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>
                      {fmtCurrency(String(b.net))}
                    </span>
                  </div>
                ));
              })()}
            </div>
            <div className="mt-2 flex items-center gap-4 text-[10px] text-[var(--muted-foreground)]">
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded-sm bg-[var(--primary)] opacity-80" /> Long
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-4 rounded-sm bg-[var(--destructive)] opacity-60" /> Short
              </span>
            </div>
          </div>
        </SectionPanel>
      )}

      {/* Top & Bottom Movers */}
      {(movers.top.length > 0 || movers.bottom.length > 0) && (
        <SectionPanel title="Top & Bottom Movers">
          <div className="p-3">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <p className="mb-1.5 text-[10px] font-medium uppercase text-[var(--success)]">Gainers</p>
                <HBarChart items={movers.top} />
              </div>
              <div>
                <p className="mb-1.5 text-[10px] font-medium uppercase text-[var(--destructive)]">Losers</p>
                <HBarChart items={movers.bottom} />
              </div>
            </div>
          </div>
        </SectionPanel>
      )}
    </div>
  );
}

// ─── Other Tabs ─────────────────────────────────────────────

function PositionsTab({ portfolioId }: { portfolioId: string }) {
  return <PositionTable portfolioId={portfolioId} />;
}

function OrdersTab({ portfolioId }: { portfolioId: string }) {
  return <OrderBlotter portfolioId={portfolioId} />;
}

function RiskTab({ portfolioId }: { portfolioId: string }) {
  return (
    <div className="space-y-3">
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Risk Summary</h2>
        <RiskSummaryCard portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Exposure</h2>
        <ExposureSummary portfolioId={portfolioId} />
      </section>
      <ExposureHistoryChart portfolioId={portfolioId} />
      <RiskHistoryChart portfolioId={portfolioId} />
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Stress Tests</h2>
        <StressTable portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Custom Stress Test</h2>
        <CustomStressForm portfolioId={portfolioId} />
      </section>
    </div>
  );
}

function CashTab({ portfolioId }: { portfolioId: string }) {
  return (
    <div className="space-y-3">
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Cash Balances</h2>
        <CashSummaryCard portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">FX Hedging</h2>
        <FXSummaryCards portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">FX Forwards</h2>
        <ForwardsTable portfolioId={portfolioId} />
      </section>
    </div>
  );
}

function AttributionTab({ portfolioId }: { portfolioId: string }) {
  return (
    <div className="space-y-3">
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Attribution Summary</h2>
        <AttributionSummaryCard portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">Transaction Cost Analysis</h2>
        <TCADashboard portfolioId={portfolioId} />
      </section>
    </div>
  );
}
