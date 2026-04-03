const STATE_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  pending_compliance: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-700",
  rejected: "bg-red-100 text-red-700",
  sent: "bg-indigo-100 text-indigo-700",
  partially_filled: "bg-purple-100 text-purple-700",
  filled: "bg-green-100 text-green-700",
  cancelled: "bg-gray-100 text-gray-500",
};

const STATE_LABELS: Record<string, string> = {
  draft: "Draft",
  pending_compliance: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  sent: "Sent",
  partially_filled: "Partial",
  filled: "Filled",
  cancelled: "Cancelled",
};

export function OrderStateBadge({ state }: { state: string }) {
  const color = STATE_COLORS[state] ?? "bg-gray-100 text-gray-700";
  const label = STATE_LABELS[state] ?? state;

  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}
