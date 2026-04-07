"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { clientFetch } from "@/shared/lib/api";

interface FundOverviewMetrics {
  total_aum: string;
  total_realized_pnl: string;
  total_unrealized_pnl: string;
  portfolio_count: number;
}

interface ViolationSummary {
  id: string;
  severity: string;
}

interface OrderSummary {
  state: string;
}

const fmtCurrency = (v: string | number) =>
  Number(v).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

export function HeaderStatusStrip() {
  const { fundSlug } = useFundContext();

  // Fund-level P&L
  const { data: overview } = useQuery({
    queryKey: ["fund-overview-metrics", fundSlug],
    queryFn: () =>
      clientFetch<FundOverviewMetrics>("/portfolios/aggregate", { fundSlug }),
    staleTime: 30_000,
  });

  // All violations across portfolios
  const { data: violations } = useQuery({
    queryKey: ["violations-all", fundSlug],
    queryFn: () =>
      clientFetch<ViolationSummary[]>("/compliance/violations", { fundSlug }),
    staleTime: 60_000,
  });

  // Pending orders (we check all orders and count open ones)
  const { data: allOrders } = useQuery({
    queryKey: ["orders-all", fundSlug],
    queryFn: () => clientFetch<OrderSummary[]>("/orders", { fundSlug }),
    staleTime: 30_000,
  });

  const unrealizedPnl = overview ? Number(overview.total_unrealized_pnl) : 0;
  const pnlStr = overview ? fmtCurrency(overview.total_unrealized_pnl) : "--";
  const pnlColor =
    unrealizedPnl > 0
      ? "text-[var(--success)]"
      : unrealizedPnl < 0
        ? "text-[var(--destructive)]"
        : "";

  const violationCount = violations?.length ?? 0;
  const pendingOrders = allOrders?.filter(
    (o) => o.state === "pending" || o.state === "partially_filled",
  ).length ?? 0;

  const aum = overview ? fmtCurrency(overview.total_aum) : "--";

  return (
    <div className="flex h-8 items-center gap-6 border-b border-[var(--border)] bg-[var(--background)] px-6 text-xs">
      <span className="text-[var(--muted-foreground)]">
        AUM: <span className="font-medium text-[var(--foreground)]">{aum}</span>
      </span>

      <Link
        href={`/${fundSlug}/attribution`}
        className="text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
      >
        Day P&L:{" "}
        <span className={`font-mono font-medium ${pnlColor}`}>{pnlStr}</span>
      </Link>

      <Link
        href={`/${fundSlug}/compliance`}
        className={`transition-colors ${
          violationCount > 0
            ? "text-[var(--destructive)] hover:text-[var(--destructive)]"
            : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        }`}
      >
        Violations:{" "}
        <span className="font-medium">
          {violationCount > 0 ? `${violationCount} \u26A0\uFE0F` : "0"}
        </span>
      </Link>

      <Link
        href={`/${fundSlug}/orders`}
        className="text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
      >
        Pending:{" "}
        <span className="font-medium text-[var(--foreground)]">
          {pendingOrders} order{pendingOrders !== 1 ? "s" : ""}
        </span>
      </Link>
    </div>
  );
}
