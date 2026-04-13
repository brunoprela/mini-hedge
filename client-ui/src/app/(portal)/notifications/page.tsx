"use client";

import { useState, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Wallet, ArrowDownRight, TrendingUp, Bell } from "lucide-react";
import { apiFetch } from "@/shared/lib/api";
import { ErrorState } from "@/shared/components/error-state";
import { useFunds, FundSelector } from "@/shared/components/fund-selector";
import type { SubscriptionRequestSummary, RedemptionRequestSummary } from "@/shared/types";

interface NAVHistoryPoint {
  business_date: string;
  nav: string;
  nav_per_share: string;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

export default function NotificationsPage() {
  const {
    data: fundsPage,
    isLoading: fundsLoading,
    error: fundsError,
    refetch,
  } = useFunds();
  const funds = fundsPage?.items ?? [];
  const [selectedSlug, setSelectedSlug] = useState<string>("");

  useEffect(() => {
    if (funds.length > 0 && !selectedSlug) {
      setSelectedSlug(funds[0].slug);
    }
  }, [funds, selectedSlug]);

  const slug = selectedSlug || funds[0]?.slug || "";

  const {
    data: subscriptions,
    isLoading: subsLoading,
    error: subsError,
  } = useQuery({
    queryKey: ["notif-subs", slug],
    queryFn: () =>
      apiFetch<SubscriptionRequestSummary[]>(
        `funds/${slug}/investor-ops/subscriptions`,
      ),
    enabled: !!slug,
  });

  const {
    data: redemptions,
    isLoading: redsLoading,
    error: redsError,
  } = useQuery({
    queryKey: ["notif-reds", slug],
    queryFn: () =>
      apiFetch<RedemptionRequestSummary[]>(
        `funds/${slug}/investor-ops/redemptions`,
      ),
    enabled: !!slug,
  });

  const {
    data: navHistory,
    isLoading: navLoading,
    error: navError,
  } = useQuery({
    queryKey: ["notif-nav", slug],
    queryFn: () =>
      apiFetch<NAVHistoryPoint[]>(
        `eod/nav/history?fund_slug=${slug}&period=30d`,
      ),
    enabled: !!slug,
  });

  const pendingSubs = useMemo(
    () =>
      (subscriptions ?? []).filter(
        (s) => s.state !== "executed" && s.state !== "cancelled",
      ),
    [subscriptions],
  );

  const pendingReds = useMemo(
    () =>
      (redemptions ?? []).filter(
        (r) => r.state !== "executed" && r.state !== "cancelled",
      ),
    [redemptions],
  );

  const recentNav = useMemo(() => {
    const sorted = [...(navHistory ?? [])].sort(
      (a, b) =>
        new Date(b.business_date).getTime() -
        new Date(a.business_date).getTime(),
    );
    return sorted.slice(0, 10);
  }, [navHistory]);

  const isLoading = fundsLoading || subsLoading || redsLoading || navLoading;
  const error = fundsError || subsError || redsError || navError;

  if (error) {
    return <ErrorState message={String(error)} onRetry={() => refetch()} />;
  }

  const hasPending = pendingSubs.length > 0 || pendingReds.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">
            Notifications
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Alerts and upcoming events
          </p>
        </div>
      </div>

      {/* Fund Selector */}
      {funds.length > 1 && (
        <div className="flex items-center gap-2">
          <label className="text-sm text-[var(--muted-foreground)]">Fund:</label>
          <FundSelector
            funds={funds}
            value={slug}
            onChange={setSelectedSlug}
          />
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : (
        <>
          {/* Section 1: Pending Activity */}
          <div className="space-y-3">
            <h2 className="text-lg font-medium text-[var(--foreground)]">
              Pending Activity
            </h2>

            {!hasPending ? (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 text-center">
                <Bell
                  size={24}
                  className="mx-auto mb-2 text-[var(--muted-foreground)]"
                />
                <p className="text-sm text-[var(--muted-foreground)]">
                  No pending activity
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {pendingSubs.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-start gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
                  >
                    <div className="rounded-full bg-[var(--warning-muted)] p-2">
                      <Wallet size={16} className="text-[var(--warning)]" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-[var(--foreground)]">
                        Subscription Request &mdash;{" "}
                        {formatCurrency(Number(s.requested_amount))}
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        Submitted on{" "}
                        {new Date(s.submitted_at).toLocaleDateString()} &bull;
                        Status: {s.state.replace(/_/g, " ")}
                      </p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        s.state === "executed"
                          ? "bg-[var(--success-muted)] text-[var(--success)]"
                          : "bg-[var(--warning-muted)] text-[var(--warning)]"
                      }`}
                    >
                      {s.state.replace(/_/g, " ")}
                    </span>
                  </div>
                ))}

                {pendingReds.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-start gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4"
                  >
                    <div className="rounded-full bg-[var(--warning-muted)] p-2">
                      <ArrowDownRight
                        size={16}
                        className="text-[var(--warning)]"
                      />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-[var(--foreground)]">
                        Redemption Request &mdash;{" "}
                        {formatCurrency(Number(r.requested_amount))}
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        Submitted on{" "}
                        {new Date(r.submitted_at).toLocaleDateString()} &bull;
                        Status: {r.state.replace(/_/g, " ")}
                      </p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        r.state === "executed"
                          ? "bg-[var(--success-muted)] text-[var(--success)]"
                          : "bg-[var(--warning-muted)] text-[var(--warning)]"
                      }`}
                    >
                      {r.state.replace(/_/g, " ")}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Section 2: Recent Fund Events */}
          <div className="space-y-3">
            <h2 className="text-lg font-medium text-[var(--foreground)]">
              Recent Fund Events
            </h2>

            {recentNav.length === 0 ? (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 text-center">
                <p className="text-sm text-[var(--muted-foreground)]">
                  No recent events
                </p>
              </div>
            ) : (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]">
                {recentNav.map((point) => (
                  <div
                    key={point.business_date}
                    className="flex items-center gap-3 px-4 py-3"
                  >
                    <div className="rounded-full bg-[var(--primary-muted)] p-2">
                      <TrendingUp
                        size={16}
                        className="text-[var(--primary)]"
                      />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-[var(--foreground)]">
                        NAV Updated &mdash;{" "}
                        {formatCurrency(Number(point.nav))}
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {new Date(point.business_date).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
