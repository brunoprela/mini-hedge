const STATE_COLORS: Record<string, string> = {
  draft: "bg-[var(--muted)] text-[var(--muted-foreground)]",
  pending_compliance: "bg-[var(--warning-muted)] text-[var(--warning)]",
  approved: "bg-[var(--primary-muted)] text-[var(--primary)]",
  rejected: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
  sent: "bg-[var(--primary-muted)] text-[var(--primary)]",
  working: "bg-[var(--info-muted,var(--primary-muted))] text-[var(--info,var(--primary))]",
  partially_filled: "bg-[var(--accent-purple-muted)] text-[var(--accent-purple)]",
  filled: "bg-[var(--success-muted)] text-[var(--success)]",
  cancelled: "bg-[var(--muted)] text-[var(--muted-foreground)]",
};

const STATE_LABELS: Record<string, string> = {
  draft: "Draft",
  pending_compliance: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  sent: "Sent",
  working: "Working",
  partially_filled: "Partial",
  filled: "Filled",
  cancelled: "Cancelled",
};

export function OrderStateBadge({ state }: { state: string }) {
  const color = STATE_COLORS[state] ?? "bg-[var(--muted)] text-[var(--muted-foreground)]";
  const label = STATE_LABELS[state] ?? state;

  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

const ALGO_LABELS: Record<string, string> = {
  twap: "TWAP",
  vwap: "VWAP",
  iceberg: "ICE",
};

export function AlgoTypeBadge({ algoType }: { algoType: string }) {
  const label = ALGO_LABELS[algoType] ?? algoType.toUpperCase();
  return (
    <span className="inline-block rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-[var(--muted-foreground)]">
      {label}
    </span>
  );
}
