"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo } from "react";
import { cumulativeQueryOptions } from "@/features/attribution/api";
import { AttributionSummaryCard } from "@/features/attribution/components/attribution-summary-card";
import { CashSummaryCard } from "@/features/cash/components/cash-summary-card";
import { ComplianceBanner } from "@/features/compliance/components/compliance-banner";
import { exposureQueryOptions } from "@/features/exposure/api";
import { ExposureHistoryChart } from "@/features/exposure/components/exposure-history-chart";
import { ExposureSummary } from "@/features/exposure/components/exposure-summary";
import { ForwardsTable, FXSummaryCards } from "@/features/fx-hedging";
import { ordersQueryOptions } from "@/features/orders/api";
import { OrderBlotter } from "@/features/orders/components/order-blotter";
import { portfolioSummaryQueryOptions, positionsQueryOptions } from "@/features/portfolio/api";
import { PositionTable } from "@/features/portfolio/components/position-table";
import { riskSnapshotQueryOptions } from "@/features/risk/api";
import { CustomStressForm } from "@/features/risk/components/custom-stress-form";
import { RiskHistoryChart } from "@/features/risk/components/risk-history-chart";
import { RiskSummaryCard } from "@/features/risk/components/risk-summary-card";
import { StressTable } from "@/features/risk/components/stress-table";
import { TCADashboard } from "@/features/tca/components/tca-dashboard";
import { DonutChart, GaugeBar, HBarChart, LineChart } from "@/shared/components/charts";
import { CollapsibleSection } from "@/shared/components/collapsible-section";
import { SectionPanel } from "@/shared/components/section-panel";
import { useTradeTicket } from "@/shared/components/trade-ticket-provider";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

const _fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

// ─── Main Component ─────────────────────────────────────────

export function PortfolioDetailClient({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const { openTradeTicket } = useTradeTicket();

  // Data queries
  const { data: summary } = useQuery(portfolioSummaryQueryOptions(fundSlug, portfolioId));
  const { data: risk } = useQuery(riskSnapshotQueryOptions(fundSlug, portfolioId));
  const { data: exposure } = useQuery(exposureQueryOptions(fundSlug, portfolioId));
  const { data: positions } = useQuery(positionsQueryOptions(fundSlug, portfolioId));
  const { data: orders } = useQuery({
    ...ordersQueryOptions(fundSlug, portfolioId),
    enabled: can(Permission.ORDERS_READ),
  });

  // Derived: open orders count
  const openOrderCount = useMemo(() => {
    if (!orders) return 0;
    return orders.filter((o) =>
      ["pending", "partially_filled", "working", "sent"].includes(o.state),
    ).length;
  }, [orders]);

  // Performance data
  const end = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const start = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  }, []);
  const { data: perfData } = useQuery(cumulativeQueryOptions(fundSlug, portfolioId, start, end));

  // Derived data
  const varValue = risk ? Math.abs(Number(risk.var_95_1d)) : 0;
  const varLimit = 200_000;

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
      .slice(0, 8);
  }, [exposure]);

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

  const movers = useMemo(() => {
    if (!positions) return { top: [], bottom: [] };
    const sorted = positions
      .map((p) => ({ label: p.instrument_id, value: Number(p.unrealized_pnl) }))
      .sort((a, b) => b.value - a.value);
    return { top: sorted.slice(0, 5), bottom: sorted.slice(-5).reverse() };
  }, [positions]);

  // Net exposure for summary strip
  const netExposure = useMemo(() => {
    if (!exposure) return null;
    return Number(exposure.net_exposure ?? 0);
  }, [exposure]);

  const grossExposure = useMemo(() => {
    if (!exposure) return null;
    return Number(exposure.gross_exposure ?? 0);
  }, [exposure]);

  return (
    <div className="space-y-3">
      <ComplianceBanner portfolioId={portfolioId} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Portfolio</h1>
        <div className="flex items-center gap-2">
          {can(Permission.TRADES_EXECUTE) && (
            <button
              type="button"
              onClick={() => openTradeTicket({ portfolioId })}
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
            >
              <Plus className="h-3.5 w-3.5" />
              New Order
            </button>
          )}
        </div>
      </div>

      {/* Dense KPI summary strip — Tailwind UI stats/05-shared-borders pattern */}
      {summary && (
        <dl className="grid auto-cols-fr grid-flow-col gap-px overflow-hidden rounded-lg bg-[var(--border)]">
          <KpiCell label="NAV" value={fmtCurrency(summary.total_market_value)} />
          <KpiCell
            label="Unrealized P&L"
            value={fmtCurrency(summary.total_unrealized_pnl)}
            color={
              Number(summary.total_unrealized_pnl) >= 0 ? "var(--success)" : "var(--destructive)"
            }
            delta={Number(summary.total_unrealized_pnl)}
          />
          <KpiCell
            label="Realized P&L"
            value={fmtCurrency(summary.total_realized_pnl)}
            color={
              Number(summary.total_realized_pnl) >= 0 ? "var(--success)" : "var(--destructive)"
            }
            delta={Number(summary.total_realized_pnl)}
          />
          <KpiCell label="Positions" value={String(summary.position_count)} />
          <KpiCell label="Open Orders" value={String(openOrderCount)} />
          {risk && (
            <KpiCell
              label="VaR 95%"
              value={fmtCurrency(risk.var_95_1d)}
              color="var(--warning)"
            />
          )}
          {grossExposure !== null && (
            <KpiCell label="Gross Exp" value={fmtCurrency(grossExposure)} />
          )}
          {netExposure !== null && (
            <KpiCell
              label="Net Exp"
              value={fmtCurrency(netExposure)}
              color={netExposure >= 0 ? "var(--success)" : "var(--destructive)"}
              delta={netExposure}
            />
          )}
        </dl>
      )}

      {/* ── Charts Row: Performance + Sector + Risk ── */}
      <CollapsibleSection title="Overview">
        <div className="grid grid-cols-12 gap-3">
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

          <div className="col-span-3">
            <SectionPanel title="Risk">
              <div className="p-3">
                <GaugeBar value={varValue} max={varLimit} label="VaR 95% (1d) Utilization" />
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
      </CollapsibleSection>

      {/* ── Currency Exposure ── */}
      {currencyBars.length > 0 && (
        <CollapsibleSection title="Currency Exposure">
          <div className="space-y-2">
            {(() => {
              const maxVal = Math.max(...currencyBars.map((b) => Math.max(b.long, b.short)), 1);
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
        </CollapsibleSection>
      )}

      {/* ── Top & Bottom Movers ── */}
      {(movers.top.length > 0 || movers.bottom.length > 0) && (
        <CollapsibleSection title="Top & Bottom Movers">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <p className="mb-1.5 text-[10px] font-medium uppercase text-[var(--success)]">
                Gainers
              </p>
              <HBarChart items={movers.top} />
            </div>
            <div>
              <p className="mb-1.5 text-[10px] font-medium uppercase text-[var(--destructive)]">
                Losers
              </p>
              <HBarChart items={movers.bottom} />
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* ── Positions ── */}
      <CollapsibleSection title="Positions">
        <PositionTable portfolioId={portfolioId} />
      </CollapsibleSection>

      {/* ── Orders ── */}
      <CollapsibleSection title="Orders">
        <OrderBlotter portfolioId={portfolioId} />
      </CollapsibleSection>

      {/* ── Collapsible: Risk & Exposure Details ── */}
      <CollapsibleSection title="Risk & Exposure Details" defaultOpen={false}>
        <div className="space-y-3">
          <RiskSummaryCard portfolioId={portfolioId} />
          <ExposureSummary portfolioId={portfolioId} />
          <ExposureHistoryChart portfolioId={portfolioId} />
          <RiskHistoryChart portfolioId={portfolioId} />
          <StressTable portfolioId={portfolioId} />
          <CustomStressForm portfolioId={portfolioId} />
        </div>
      </CollapsibleSection>

      {/* ── Collapsible: Cash & FX ── */}
      <CollapsibleSection title="Cash & FX" defaultOpen={false}>
        <div className="space-y-3">
          <CashSummaryCard portfolioId={portfolioId} />
          <FXSummaryCards portfolioId={portfolioId} />
          <ForwardsTable portfolioId={portfolioId} />
        </div>
      </CollapsibleSection>

      {/* ── Collapsible: Attribution & TCA ── */}
      <CollapsibleSection title="Attribution & TCA" defaultOpen={false}>
        <div className="space-y-3">
          <AttributionSummaryCard portfolioId={portfolioId} />
          <TCADashboard portfolioId={portfolioId} />
        </div>
      </CollapsibleSection>
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────

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

/**
 * Dense KPI cell for the summary strip.
 * Label on top, value below, optional delta triangle for P&L values.
 */
function KpiCell({
  label,
  value,
  color,
  delta,
}: {
  label: string;
  value: string;
  color?: string;
  /** Numeric value used to show an up/down/flat delta triangle. */
  delta?: number;
}) {
  const direction = delta != null && isFinite(delta) ? (delta > 0 ? "up" : delta < 0 ? "down" : "flat") : null;
  const arrow = direction === "up" ? "\u25B2" : direction === "down" ? "\u25BC" : null;
  const arrowColor =
    direction === "up"
      ? "var(--success)"
      : direction === "down"
        ? "var(--destructive)"
        : undefined;

  return (
    <div className="bg-[var(--card)] px-3 py-1.5">
      <dt className="text-[9px] uppercase tracking-wider text-[var(--muted-foreground)]">{label}</dt>
      <dd className="mt-0.5 flex items-center gap-1">
        {arrow && (
          <span className="text-[8px]" style={{ color: arrowColor }}>
            {arrow}
          </span>
        )}
        <span
          className="font-mono text-xs font-semibold leading-tight"
          style={color ? { color } : undefined}
        >
          {value}
        </span>
      </dd>
    </div>
  );
}

