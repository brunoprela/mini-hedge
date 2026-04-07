"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
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
import { LineChart, HBarChart, GaugeBar, SummaryStrip } from "@/shared/components/charts";

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
    <div className="space-y-4">
      <ComplianceBanner portfolioId={portfolioId} />

      {/* Sticky header: title + actions + tabs */}
      <div className="sticky top-0 z-10 -mx-6 border-b border-[var(--border)] bg-[var(--background)] px-6 pb-0 pt-2">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Portfolio</h1>
          <ActionBar portfolioId={portfolioId} fundSlug={fundSlug} onSwitchTab={switchTab} />
        </div>
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => switchTab(tab.id)}
              className={cn(
                "rounded-t-lg px-4 py-2 text-sm font-medium transition-colors",
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
        className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
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

function TradeTicketLazy({
  portfolioId,
  onClose,
  defaults,
}: {
  portfolioId: string;
  onClose: () => void;
  defaults?: { instrument?: string; side?: string; quantity?: string };
}) {
  const { TradeTicket } = require("@/features/portfolio/components/trade-ticket");
  return <TradeTicket portfolioId={portfolioId} onClose={onClose} defaults={defaults} />;
}

// ─── Overview Tab (Broadridge-style) ────────────────────────

function OverviewTab({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();

  // Portfolio summary
  const { data: summary } = useQuery(portfolioSummaryQueryOptions(fundSlug, portfolioId));

  // Risk snapshot
  const { data: risk } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));

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

  // Top/bottom movers
  const movers = useMemo(() => {
    if (!positions) return { top: [], bottom: [] };
    const sorted = positions
      .map((p) => ({ label: p.instrument_id, value: Number(p.unrealized_pnl) }))
      .sort((a, b) => b.value - a.value);
    return { top: sorted.slice(0, 5), bottom: sorted.slice(-5).reverse() };
  }, [positions]);

  // Summary strip items
  const stripItems = summary
    ? [
        { label: "Market Value", value: fmtCurrency(summary.total_market_value) },
        {
          label: "Unrealized P&L",
          value: fmtCurrency(summary.total_unrealized_pnl),
          color: Number(summary.total_unrealized_pnl) >= 0 ? "var(--success)" : "var(--destructive)",
        },
        {
          label: "Realized P&L",
          value: fmtCurrency(summary.total_realized_pnl),
          color: Number(summary.total_realized_pnl) >= 0 ? "var(--success)" : "var(--destructive)",
        },
        { label: "Cost Basis", value: fmtCurrency(summary.total_cost_basis) },
      ]
    : [];

  // VaR gauge
  const varValue = risk ? Math.abs(Number(risk.var_95_1d)) : 0;
  const varLimit = 200_000; // default limit — would come from fund config

  return (
    <div className="space-y-5">
      {/* Summary strip */}
      {stripItems.length > 0 && <SummaryStrip items={stripItems} />}

      {/* Performance chart + VaR gauge side by side */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Performance (30 days)
          </h3>
          {perfSeries.length > 0 ? (
            <LineChart
              series={perfSeries}
              height={220}
              formatY={(v) => `${v.toFixed(1)}%`}
              xLabelInterval={7}
            />
          ) : (
            <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
              No performance data
            </p>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              Risk
            </h3>
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
          </div>

          <ExposureSummary portfolioId={portfolioId} />
        </div>
      </div>

      {/* Top & Bottom Movers */}
      {(movers.top.length > 0 || movers.bottom.length > 0) && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Top & Bottom Movers
          </h3>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <p className="mb-2 text-[10px] font-medium uppercase text-[var(--success)]">Gainers</p>
              <HBarChart items={movers.top} />
            </div>
            <div>
              <p className="mb-2 text-[10px] font-medium uppercase text-[var(--destructive)]">Losers</p>
              <HBarChart items={movers.bottom} />
            </div>
          </div>
        </div>
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
    <div className="space-y-6">
      <section>
        <h2 className="mb-3 text-lg font-semibold">Risk Summary</h2>
        <RiskSummaryCard portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Exposure</h2>
        <ExposureSummary portfolioId={portfolioId} />
      </section>
      <ExposureHistoryChart portfolioId={portfolioId} />
      <RiskHistoryChart portfolioId={portfolioId} />
      <section>
        <h2 className="mb-3 text-lg font-semibold">Stress Tests</h2>
        <StressTable portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Custom Stress Test</h2>
        <CustomStressForm portfolioId={portfolioId} />
      </section>
    </div>
  );
}

function CashTab({ portfolioId }: { portfolioId: string }) {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-3 text-lg font-semibold">Cash Balances</h2>
        <CashSummaryCard portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">FX Hedging</h2>
        <FXSummaryCards portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">FX Forwards</h2>
        <ForwardsTable portfolioId={portfolioId} />
      </section>
    </div>
  );
}

function AttributionTab({ portfolioId }: { portfolioId: string }) {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-3 text-lg font-semibold">Attribution Summary</h2>
        <AttributionSummaryCard portfolioId={portfolioId} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Transaction Cost Analysis</h2>
        <TCADashboard portfolioId={portfolioId} />
      </section>
    </div>
  );
}
