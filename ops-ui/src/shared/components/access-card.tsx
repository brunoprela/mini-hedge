"use client";

import { ChevronDown, ChevronRight, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { PermissionBadge } from "@/shared/components/permission-badge";
import {
  effectivePermissions,
  FUND_PERMISSIONS,
  formatRelation,
  type GroupedAccess,
  PERMISSION_LABELS,
  roleGrantedPermissions,
  rolesForType,
} from "@/shared/lib/permissions";

export function AccessCard({
  entry,
  isAdmin,
  isPending,
  onToggleRole,
  onTogglePermission,
  onRemoveAll,
}: {
  entry: GroupedAccess;
  isAdmin: boolean;
  isPending: boolean;
  onToggleRole: (rel: string) => void;
  onTogglePermission: (perm: string) => void;
  onRemoveAll: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const rolePerms = useMemo(() => roleGrantedPermissions(entry.roles), [entry.roles]);
  const allPerms = useMemo(
    () => effectivePermissions(entry.roles, entry.directPermissions),
    [entry.roles, entry.directPermissions],
  );

  const isUser = entry.user_type === "user";

  return (
    <div className="rounded-lg border border-[var(--border)] bg-white">
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{entry.display_name ?? entry.user_id}</span>
            <span className="inline-block rounded-full px-2 py-0.5 text-xs bg-[var(--muted)] text-[var(--muted-foreground)]">
              {entry.user_type}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] flex items-center gap-0.5"
            >
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {allPerms.size} permissions
            </button>
            {isAdmin && (
              <button
                type="button"
                onClick={onRemoveAll}
                className="text-xs text-[var(--destructive)] hover:opacity-70 flex items-center gap-1"
                title="Remove all access"
              >
                <Trash2 size={12} /> Remove
              </button>
            )}
          </div>
        </div>

        {/* Role badges */}
        <div className="mb-3">
          <p className="text-[11px] uppercase tracking-wider text-[var(--muted-foreground)] mb-1.5 font-medium">
            Roles
          </p>
          <div className="flex flex-wrap gap-1.5">
            {rolesForType(entry.user_type).map((rel) => {
              const active = entry.roles.has(rel);
              let cls: string;
              if (active) {
                cls = "bg-[var(--primary)] text-white";
              } else if (isAdmin) {
                cls =
                  "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--accent)] cursor-pointer";
              } else {
                cls = "bg-[var(--muted)] text-[var(--muted-foreground)] opacity-40";
              }
              return (
                <button
                  key={rel}
                  type="button"
                  disabled={!isAdmin || isPending}
                  onClick={() => onToggleRole(rel)}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors disabled:cursor-not-allowed ${cls}`}
                  title={
                    isAdmin
                      ? active
                        ? `Revoke ${formatRelation(rel)}`
                        : `Grant ${formatRelation(rel)}`
                      : undefined
                  }
                >
                  {formatRelation(rel)}
                </button>
              );
            })}
          </div>
        </div>

        {/* Direct permission badges (users only) */}
        {isUser && (
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--muted-foreground)] mb-1.5 font-medium">
              Direct Permissions
            </p>
            <div className="flex flex-wrap gap-1.5">
              {FUND_PERMISSIONS.map((perm) => {
                const hasDirect = entry.directPermissions.has(perm);
                const hasViaRole = rolePerms.has(perm);
                let cls: string;
                if (hasDirect) {
                  cls = "bg-violet-600 text-white ring-1 ring-violet-400";
                } else if (hasViaRole) {
                  // Granted via role -- show as inherited (not toggleable unless admin)
                  cls = "bg-emerald-100 text-emerald-700 opacity-60";
                } else if (isAdmin) {
                  cls =
                    "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-violet-100 hover:text-violet-700 cursor-pointer";
                } else {
                  cls = "bg-[var(--muted)] text-[var(--muted-foreground)] opacity-40";
                }

                const label = PERMISSION_LABELS[perm] ?? perm;
                let title: string | undefined;
                if (hasDirect && hasViaRole) {
                  title = `${label} — granted directly AND via role (click to revoke direct grant)`;
                } else if (hasDirect) {
                  title = `${label} — direct grant (click to revoke)`;
                } else if (hasViaRole) {
                  title = `${label} — inherited from role`;
                } else if (isAdmin) {
                  title = `Grant ${label} directly`;
                }

                return (
                  <button
                    key={perm}
                    type="button"
                    disabled={!isAdmin || isPending}
                    onClick={() => onTogglePermission(perm)}
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors disabled:cursor-not-allowed ${cls}`}
                    title={title}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Expanded: effective permissions summary */}
      {expanded && (
        <div className="border-t border-[var(--border)] px-4 py-3 bg-[var(--muted)]/30">
          <p className="text-[11px] uppercase tracking-wider text-[var(--muted-foreground)] mb-2 font-medium">
            Effective Permissions
          </p>
          {allPerms.size === 0 ? (
            <p className="text-xs text-[var(--muted-foreground)]">
              No permissions — grant a role or permission above.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {Array.from(allPerms)
                .sort()
                .map((p) => {
                  const hasDirect = entry.directPermissions.has(p);
                  const hasViaRole = rolePerms.has(p);
                  const source: "role" | "direct" | "both" =
                    hasDirect && hasViaRole ? "both" : hasDirect ? "direct" : "role";
                  return <PermissionBadge key={p} perm={p} source={source} />;
                })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
