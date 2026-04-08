const SUB_COLORS: Record<string, string> = {
  draft: "bg-[var(--muted)] text-[var(--muted-foreground)]",
  pending_kyc: "bg-[var(--warning-muted)] text-[var(--warning)]",
  kyc_approved: "bg-[var(--primary-muted)] text-[var(--primary)]",
  kyc_rejected: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
  pending_ops_review: "bg-[var(--warning-muted)] text-[var(--warning)]",
  pending_gp_approval: "bg-[var(--warning-muted)] text-[var(--warning)]",
  approved: "bg-[var(--primary-muted)] text-[var(--primary)]",
  rejected: "bg-[var(--destructive-muted)] text-[var(--destructive)]",
  pending_wire: "bg-[var(--warning-muted)] text-[var(--warning)]",
  wire_confirmed: "bg-[var(--primary-muted)] text-[var(--primary)]",
  queued_for_nav: "bg-[var(--primary-muted)] text-[var(--primary)]",
  executed: "bg-[var(--success-muted)] text-[var(--success)]",
  cancelled: "bg-[var(--muted)] text-[var(--muted-foreground)]",
};

const SUB_LABELS: Record<string, string> = {
  draft: "Draft",
  pending_kyc: "Pending KYC",
  kyc_approved: "KYC Approved",
  kyc_rejected: "KYC Rejected",
  pending_ops_review: "Ops Review",
  pending_gp_approval: "GP Approval",
  approved: "Approved",
  rejected: "Rejected",
  pending_wire: "Pending Wire",
  wire_confirmed: "Wire Confirmed",
  queued_for_nav: "Queued",
  executed: "Executed",
  cancelled: "Cancelled",
};

const RED_LABELS: Record<string, string> = {
  draft: "Draft",
  pending_validation: "Validating",
  validated: "Validated",
  validation_failed: "Failed",
  pending_gate_check: "Gate Check",
  gate_applied: "Gate Applied",
  queued_for_nav: "Queued",
  nav_calculated: "NAV Calc'd",
  pending_payment: "Pending Payment",
  payment_sent: "Payment Sent",
  executed: "Executed",
  cancelled: "Cancelled",
};

export function SubscriptionStateBadge({ state }: { state: string }) {
  const color = SUB_COLORS[state] ?? "bg-[var(--muted)] text-[var(--muted-foreground)]";
  const label = SUB_LABELS[state] ?? state;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

export function RedemptionStateBadge({ state }: { state: string }) {
  const color = SUB_COLORS[state] ?? "bg-[var(--muted)] text-[var(--muted-foreground)]";
  const label = RED_LABELS[state] ?? state;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}
