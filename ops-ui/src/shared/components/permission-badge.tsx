import { PERMISSION_LABELS } from "@/shared/lib/permissions";

export function PermissionBadge({
  perm,
  source,
}: {
  perm: string;
  source: "role" | "direct" | "both";
}) {
  const isWrite = perm.includes("write") || perm.includes("execute") || perm.includes("manage");
  let cls: string;
  if (source === "direct") {
    cls = isWrite
      ? "bg-violet-100 text-violet-800 ring-1 ring-violet-300"
      : "bg-violet-50 text-violet-700 ring-1 ring-violet-200";
  } else {
    cls = isWrite ? "bg-amber-100 text-amber-800" : "bg-emerald-50 text-emerald-700";
  }
  const label = PERMISSION_LABELS[perm] ?? perm;
  const suffix = source === "direct" ? " (direct)" : source === "both" ? " (role + direct)" : "";
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-mono ${cls}`}
      title={`${label}${suffix}`}
    >
      {label}
    </span>
  );
}
