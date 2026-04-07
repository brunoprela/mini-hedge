"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { ordersQueryOptions } from "@/features/orders/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { Permission } from "@/shared/lib/permissions";
import { clientFetch } from "@/shared/lib/api";
import { HBarChart, StatusDot } from "./charts";

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
      clientFetch<{ id: string; severity: string; rule_name: string; message: string; portfolio_id: string }[]>(
        "/compliance/violations",
        { fundSlug },
      ),
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

  // Derived data
  const pendingOrders =
    orders?.filter((o) => ["pending", "partially_filled", "working", "sent"].includes(o.state))
      .length ?? 0;
  const filledToday = orders?.filter((o) => o.state === "filled").length ?? 0;
  const violationCount = violations?.length ?? 0;
  const blockCount = violations?.filter((v) => v.severity === "block").length ?? 0;

  const today = new Date().toISOString().slice(0, 10);
  const todayEod = eodRuns?.find((r) => r.run_date === today);

  const movers = (positions ?? [])
    .map((p) => ({ label: p.instrument_id, value: Number(p.unrealized_pnl) }))
    .sort((a, b) => b.value - a.value);
  const topMovers = movers.slice(0, 5);
  const bottomMovers = movers.slice(-5).reverse();

  return (
    <div className="grid h-[calc(100vh-7rem)] grid-cols-12 grid-rows-[auto_1fr_1fr] gap-3">
      {/* Row 1: Greeting + 4 KPI cards — spans full width */}
      <div className="col-span-12 flex items-center gap-4">
        <div className="shrink-0">
          <h1 className="text-lg font-semibold">
            Hello, {userName}
          </h1>
          <p className="text-xs text-[var(--muted-foreground)]">{fundName}</p>
        </div>
        <div className="flex flex-1 gap-3">
          <KpiCard label="Total AUM" value={aggregate ? fmtCurrency(aggregate.total_aum) : "--"} />
          <KpiCard
            label="Unrealized P&L"
            value={aggregate ? fmtCurrency(aggregate.total_unrealized_pnl) : "--"}
            color={
              aggregate
                ? Number(aggregate.total_unrealized_pnl) >= 0 ? "var(--success)" : "var(--destructive)"
                : undefined
            }
          />
          <KpiCard
            label="Realized P&L"
            value={aggregate ? fmtCurrency(aggregate.total_realized_pnl) : "--"}
            color={
              aggregate
                ? Number(aggregate.total_realized_pnl) >= 0 ? "var(--success)" : "var(--destructive)"
                : undefined
            }
          />
          <KpiCard label="Positions" value={aggregate ? String(aggregate.total_positions) : "--"} />
        </div>
      </div>

      {/* Row 2, Left (8 cols): Top & Bottom Movers */}
      <div className="col-span-8 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        {movers.length > 0 ? (
          <>
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              Top & Bottom Movers — Unrealized P&L
            </h3>
            <div className="grid h-[calc(100%-24px)] grid-cols-2 gap-6">
              <div>
                <p className="mb-2 text-[10px] font-medium uppercase text-[var(--success)]">
                  Top Gainers
                </p>
                <HBarChart items={topMovers} />
              </div>
              <div>
                <p className="mb-2 text-[10px] font-medium uppercase text-[var(--destructive)]">
                  Top Losers
                </p>
                <HBarChart items={bottomMovers} />
              </div>
            </div>
          </>
        ) : (
          <p className="text-sm text-[var(--muted-foreground)]">No positions yet</p>
        )}
      </div>

      {/* Row 2, Right (4 cols): Today's Status */}
      <div className="col-span-4 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Today&apos;s Status
        </h3>
        <div className="space-y-2">
          <StatusRow
            label="Pending Orders"
            value={String(pendingOrders)}
            variant={pendingOrders > 0 ? "info" : "neutral"}
            href={`/${fundSlug}/orders`}
          />
          <StatusRow
            label="Filled Orders"
            value={String(filledToday)}
            variant={filledToday > 0 ? "success" : "neutral"}
            href={`/${fundSlug}/orders`}
          />
          <StatusRow
            label="Compliance"
            value={violationCount > 0 ? `${violationCount} (${blockCount} blocks)` : "Clear"}
            variant={blockCount > 0 ? "error" : violationCount > 0 ? "warning" : "success"}
            href={`/${fundSlug}/compliance`}
          />
          <StatusRow
            label="EOD"
            value={
              todayEod
                ? todayEod.status === "completed"
                  ? "Complete"
                  : todayEod.status === "failed"
                    ? "Failed"
                    : "Running"
                : "Not run"
            }
            variant={
              todayEod?.status === "completed"
                ? "success"
                : todayEod?.status === "failed"
                  ? "error"
                  : "neutral"
            }
            href={`/${fundSlug}/eod`}
          />
        </div>

        {/* Compliance alerts inline */}
        {can(Permission.COMPLIANCE_READ) && violations && violations.length > 0 && (
          <div className="mt-4 border-t border-[var(--border)] pt-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                Alerts
              </p>
              <Link
                href={`/${fundSlug}/compliance`}
                className="text-[10px] text-[var(--primary)] hover:underline"
              >
                View all
              </Link>
            </div>
            <div className="space-y-1.5">
              {violations.slice(0, 4).map((v) => (
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
                    <span className="font-medium text-[var(--foreground)]">{v.rule_name}</span>
                    <p className="truncate text-[var(--muted-foreground)]">{v.message}</p>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Row 3, Left (5 cols): Portfolios */}
      <div className="col-span-5 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div className="px-4 py-3">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Portfolios
          </h3>
        </div>
        {portfolios && portfolios.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
                <th className="px-4 py-1.5 font-medium">Name</th>
                <th className="px-4 py-1.5 font-medium">Strategy</th>
                <th className="px-4 py-1.5" />
              </tr>
            </thead>
            <tbody>
              {portfolios.map((p) => (
                <tr
                  key={p.id}
                  className="border-t border-[var(--table-border)] hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-4 py-1.5 font-medium">
                    <Link
                      href={`/${fundSlug}/portfolio/${p.id}`}
                      className="hover:text-[var(--primary)]"
                    >
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-1.5 text-[var(--muted-foreground)]">
                    {p.strategy ?? "—"}
                  </td>
                  <td className="px-4 py-1.5 text-right">
                    <Link
                      href={`/${fundSlug}/portfolio/${p.id}`}
                      className="text-xs text-[var(--primary)] hover:underline"
                    >
                      Open &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="px-4 pb-4 text-sm text-[var(--muted-foreground)]">No portfolios</p>
        )}
      </div>

      {/* Row 3, Right (7 cols): Recent Orders */}
      <div className="col-span-7 overflow-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div className="flex items-center justify-between px-4 py-3">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Recent Orders
          </h3>
          {can(Permission.ORDERS_READ) && (
            <Link
              href={`/${fundSlug}/orders`}
              className="text-xs text-[var(--primary)] hover:underline"
            >
              View all
            </Link>
          )}
        </div>
        {can(Permission.ORDERS_READ) && orders && orders.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
                <th className="px-4 py-1.5 font-medium">Instrument</th>
                <th className="px-4 py-1.5 font-medium">Side</th>
                <th className="px-4 py-1.5 font-medium text-right">Qty</th>
                <th className="px-4 py-1.5 font-medium">State</th>
                <th className="px-4 py-1.5 font-medium text-right">Time</th>
              </tr>
            </thead>
            <tbody>
              {orders.slice(0, 8).map((o) => (
                <tr
                  key={o.id}
                  className="border-t border-[var(--table-border)] hover:bg-[var(--table-row-hover)]"
                >
                  <td className="px-4 py-1.5 font-mono font-medium">
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
                    {o.instrument_id}
                  </td>
                  <td className="px-4 py-1.5">
                    <span
                      className={`text-xs font-medium ${
                        o.side === "buy" ? "text-[var(--success)]" : "text-[var(--destructive)]"
                      }`}
                    >
                      {o.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-1.5 text-right font-mono text-xs">
                    {parseFloat(o.quantity).toLocaleString()}
                  </td>
                  <td className="px-4 py-1.5 text-xs text-[var(--muted-foreground)]">
                    {o.state}
                  </td>
                  <td className="px-4 py-1.5 text-right text-xs text-[var(--muted-foreground)]">
                    {new Date(o.created_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="px-4 pb-4 text-sm text-[var(--muted-foreground)]">No orders yet</p>
        )}
      </div>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
        {label}
      </p>
      <p
        className="mt-0.5 font-mono text-lg font-semibold"
        style={color ? { color } : undefined}
      >
        {value}
      </p>
    </div>
  );
}

function StatusRow({
  label,
  value,
  variant,
  href,
}: {
  label: string;
  value: string;
  variant: "success" | "warning" | "error" | "info" | "neutral";
  href: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-md px-2 py-1 transition-colors hover:bg-[var(--muted)]"
    >
      <div className="flex items-center gap-2">
        <StatusDot variant={variant} size={7} />
        <span className="text-xs text-[var(--foreground)]">{label}</span>
      </div>
      <span className="text-xs font-medium text-[var(--muted-foreground)]">{value}</span>
    </Link>
  );
}
