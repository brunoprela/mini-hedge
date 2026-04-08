"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Plus } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { cumulativeQueryOptions } from "@/features/attribution/api";
import { AttributionSummaryCard } from "@/features/attribution/components/attribution-summary-card";
import { CashSummaryCard } from "@/features/cash/components/cash-summary-card";
import { ComplianceBanner } from "@/features/compliance/components/compliance-banner";
import { exposureQueryOptions } from "@/features/exposure/api";
import { ExposureHistoryChart } from "@/features/exposure/components/exposure-history-chart";
import { ExposureSummary } from "@/features/exposure/components/exposure-summary";
import { ForwardsTable, FXSummaryCards } from "@/features/fx-hedging";
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

      {/* Dense summary strip */}
      {summary && (
        <div className="flex items-center gap-4 rounded-md border border-[var(--border)] bg-[var(--card)] px-4 py-2">
          <StripItem label="Market Value" value={fmtCurrency(summary.total_market_value)} />
          <StripDivider />
          <StripItem
            label="Unrealized P&L"
            value={fmtCurrency(summary.total_unrealized_pnl)}
            color={
              Number(summary.total_unrealized_pnl) >= 0 ? "var(--success)" : "var(--destructive)"
            }
          />
          <StripDivider />
          <StripItem
            label="Realized P&L"
            value={fmtCurrency(summary.total_realized_pnl)}
            color={
              Number(summary.total_realized_pnl) >= 0 ? "var(--success)" : "var(--destructive)"
            }
          />
          <StripDivider />
          <StripItem label="Positions" value={String(summary.position_count)} />
          <StripDivider />
          <StripItem label="Cost Basis" value={fmtCurrency(summary.total_cost_basis)} />
          {risk && (
            <>
              <StripDivider />
              <StripItem
                label="VaR 95%"
                value={fmtCurrency(risk.var_95_1d)}
                color="var(--warning)"
              />
            </>
          )}
          {grossExposure !== null && (
            <>
              <StripDivider />
              <StripItem label="Gross Exp" value={fmtCurrency(grossExposure)} />
            </>
          )}
          {netExposure !== null && (
            <>
              <StripDivider />
              <StripItem
                label="Net Exp"
                value={fmtCurrency(netExposure)}
                color={netExposure >= 0 ? "var(--success)" : "var(--destructive)"}
              />
            </>
          )}
        </div>
      )}

      {/* ── Charts Row: Performance + Sector + Risk ── */}
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

      {/* ── Currency Exposure ── */}
      {currencyBars.length > 0 && (
        <SectionPanel title="Currency Exposure">
          <div className="p-3">
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
          </div>
        </SectionPanel>
      )}

      {/* ── Top & Bottom Movers ── */}
      {(movers.top.length > 0 || movers.bottom.length > 0) && (
        <SectionPanel title="Top & Bottom Movers">
          <div className="p-3">
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
          </div>
        </SectionPanel>
      )}

      {/* ── Positions ── */}
      <PositionTable portfolioId={portfolioId} />

      {/* ── Orders ── */}
      <OrderBlotter portfolioId={portfolioId} />

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

function StripItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <p className="font-mono text-sm font-bold" style={color ? { color } : undefined}>
        {value}
      </p>
      <p className="text-[9px] uppercase tracking-wider text-[var(--muted-foreground)]">{label}</p>
    </div>
  );
}

function StripDivider() {
  return <div className="h-6 w-px bg-[var(--border)]" />;
}

function CollapsibleSection({
  title,
  defaultOpen,
  children,
}: {
  title: string;
  defaultOpen: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-md border border-[var(--border)]">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between bg-[var(--primary-muted)] px-3 py-2 text-left"
      >
        <span className="text-xs font-semibold text-[var(--foreground)]">{title}</span>
        <ChevronDown
          className={`h-4 w-4 text-[var(--muted-foreground)] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="bg-[var(--card)] p-3">{children}</div>}
    </div>
  );
}
