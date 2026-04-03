const VARIANTS = {
  success: "bg-green-100 text-green-700",
  warning: "bg-yellow-100 text-yellow-700",
  danger: "bg-red-100 text-red-700",
  neutral: "bg-[var(--muted)] text-[var(--muted-foreground)]",
} as const;

export function StatusBadge({
  label,
  variant = "neutral",
}: {
  label: string;
  variant?: keyof typeof VARIANTS;
}) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${VARIANTS[variant]}`}
    >
      {label}
    </span>
  );
}
