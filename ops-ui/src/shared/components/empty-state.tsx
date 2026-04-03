import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Icon size={40} className="text-[var(--muted-foreground)] mb-3" />
      <p className="text-sm font-medium text-[var(--foreground)]">{title}</p>
      {description && <p className="text-sm text-[var(--muted-foreground)] mt-1">{description}</p>}
    </div>
  );
}
