"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { feeScheduleQueryOptions } from "../api";

export function FeeScheduleCard() {
  const { fundSlug } = useFundContext();
  const { data: schedule, isLoading } = useQuery(feeScheduleQueryOptions(fundSlug));

  if (isLoading) {
    return <div className="text-sm text-[var(--muted-foreground)]">Loading fee schedule...</div>;
  }

  if (!schedule) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
        No fee schedule configured for this fund.
      </div>
    );
  }

  const items = [
    { label: "Management Fee", value: `${schedule.management_fee_bps} bps` },
    {
      label: "Performance Fee",
      value: `${(Number(schedule.performance_fee_pct) * 100).toFixed(1)}%`,
    },
    { label: "Hurdle Rate", value: `${(Number(schedule.hurdle_rate_pct) * 100).toFixed(1)}%` },
    { label: "High Water Mark", value: schedule.high_water_mark ? "Yes" : "No" },
    { label: "Crystallization", value: schedule.crystallization_frequency },
    { label: "Payment", value: schedule.payment_frequency },
  ];

  return (
    <div className="rounded-lg border border-[var(--border)] p-4">
      <h3 className="mb-3 text-sm font-semibold">Fee Schedule</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((item) => (
          <div key={item.label}>
            <p className="text-xs text-[var(--muted-foreground)]">{item.label}</p>
            <p className="text-sm font-medium">{item.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
