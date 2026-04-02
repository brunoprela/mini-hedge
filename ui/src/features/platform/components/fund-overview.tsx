"use client";

import { useFundContext } from "@/shared/hooks/use-fund-context";

export function FundOverview({ fundSlug }: { fundSlug: string }) {
  const { fundName, role } = useFundContext();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{fundName}</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Role: {role ?? "loading..."}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Fund" value={fundSlug} />
        <MetricCard label="Role" value={role ?? "-"} />
        <MetricCard label="Status" value="Active" />
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] p-4">
      <p className="text-sm text-[var(--muted-foreground)]">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}
