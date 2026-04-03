"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { use, useMemo, useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/shared/lib/api";
import { useRole } from "@/shared/lib/use-role";

interface FundAccessGrant {
  user_type: string;
  user_id: string;
  relation: string;
  relation_type: "role" | "permission";
  display_name: string | null;
}

interface GroupedAccess {
  user_type: string;
  user_id: string;
  display_name: string | null;
  roles: Set<string>;
  directPermissions: Set<string>;
}

// --- Role & permission definitions ---

const USER_ROLES = [
  "admin",
  "portfolio_manager",
  "analyst",
  "risk_manager",
  "compliance",
  "viewer",
];
const OPERATOR_RELATIONS = ["ops_full", "ops_read"];

// All individual permissions that can be directly granted
const FUND_PERMISSIONS = [
  "can_read_instruments",
  "can_write_instruments",
  "can_read_prices",
  "can_read_positions",
  "can_write_positions",
  "can_execute_trades",
  "can_read_fund",
  "can_manage_fund",
];

// Platform-level permissions for operators
const PLATFORM_PERMISSIONS = [
  "platform:users.read",
  "platform:users.write",
  "platform:funds.read",
  "platform:funds.write",
  "platform:operators.read",
  "platform:operators.write",
  "platform:audit.read",
  "platform:access.read",
  "platform:access.write",
];

// FGA relation name → human-readable permission label
const PERMISSION_LABELS: Record<string, string> = {
  can_read_instruments: "Instruments Read",
  can_write_instruments: "Instruments Write",
  can_read_prices: "Prices Read",
  can_read_positions: "Positions Read",
  can_write_positions: "Positions Write",
  can_execute_trades: "Trades Execute",
  can_read_fund: "Fund Read",
  can_manage_fund: "Fund Manage",
  "platform:users.read": "Users Read",
  "platform:users.write": "Users Write",
  "platform:funds.read": "Funds Read",
  "platform:funds.write": "Funds Write",
  "platform:operators.read": "Operators Read",
  "platform:operators.write": "Operators Write",
  "platform:audit.read": "Audit Read",
  "platform:access.read": "Access Read",
  "platform:access.write": "Access Write",
};

// Which roles grant which permissions (mirrors FGA model computed unions)
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: FUND_PERMISSIONS, // all
  portfolio_manager: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_write_positions",
    "can_execute_trades",
    "can_read_fund",
  ],
  analyst: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
  ],
  risk_manager: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
  ],
  compliance: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
  ],
  viewer: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
  ],
  ops_full: PLATFORM_PERMISSIONS, // all platform permissions
  ops_read: [
    "platform:users.read",
    "platform:funds.read",
    "platform:operators.read",
    "platform:audit.read",
    "platform:access.read",
  ],
};

function rolesForType(type: string) {
  return type === "user" ? USER_ROLES : OPERATOR_RELATIONS;
}

function formatRelation(r: string) {
  return r.replace(/_/g, " ");
}

/** Compute the set of permissions granted by the user's active roles. */
function roleGrantedPermissions(roles: Set<string>): Set<string> {
  const perms = new Set<string>();
  for (const role of roles) {
    for (const p of ROLE_PERMISSIONS[role] ?? []) {
      perms.add(p);
    }
  }
  return perms;
}

/** Compute the full effective permissions: role-granted + direct grants. */
function effectivePermissions(
  roles: Set<string>,
  directPerms: Set<string>,
): Set<string> {
  const perms = roleGrantedPermissions(roles);
  for (const p of directPerms) {
    perms.add(p);
  }
  return perms;
}

function PermissionBadge({
  perm,
  source,
}: {
  perm: string;
  source: "role" | "direct" | "both";
}) {
  const isWrite =
    perm.includes("write") ||
    perm.includes("execute") ||
    perm.includes("manage");
  let cls: string;
  if (source === "direct") {
    cls = isWrite
      ? "bg-violet-100 text-violet-800 ring-1 ring-violet-300"
      : "bg-violet-50 text-violet-700 ring-1 ring-violet-200";
  } else {
    cls = isWrite
      ? "bg-amber-100 text-amber-800"
      : "bg-emerald-50 text-emerald-700";
  }
  const label = PERMISSION_LABELS[perm] ?? perm;
  const suffix =
    source === "direct" ? " (direct)" : source === "both" ? " (role + direct)" : "";
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-mono ${cls}`}
      title={`${label}${suffix}`}
    >
      {label}
    </span>
  );
}

function AccessCard({
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

  const rolePerms = useMemo(
    () => roleGrantedPermissions(entry.roles),
    [entry.roles],
  );
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
            <span className="font-medium text-sm">
              {entry.display_name ?? entry.user_id}
            </span>
            <span
              className="inline-block rounded-full px-2 py-0.5 text-xs bg-[var(--muted)] text-[var(--muted-foreground)]"
            >
              {entry.user_type}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] flex items-center gap-0.5"
            >
              {expanded ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              )}
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
                cls =
                  "bg-[var(--muted)] text-[var(--muted-foreground)] opacity-40";
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
                  cls =
                    "bg-violet-600 text-white ring-1 ring-violet-400";
                } else if (hasViaRole) {
                  // Granted via role — show as inherited (not toggleable unless admin)
                  cls =
                    "bg-emerald-100 text-emerald-700 opacity-60";
                } else if (isAdmin) {
                  cls =
                    "bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-violet-100 hover:text-violet-700 cursor-pointer";
                } else {
                  cls =
                    "bg-[var(--muted)] text-[var(--muted-foreground)] opacity-40";
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
              {Array.from(allPerms).sort().map((p) => {
                const hasDirect = entry.directPermissions.has(p);
                const hasViaRole = rolePerms.has(p);
                const source: "role" | "direct" | "both" =
                  hasDirect && hasViaRole
                    ? "both"
                    : hasDirect
                      ? "direct"
                      : "role";
                return <PermissionBadge key={p} perm={p} source={source} />;
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function FundAccessPage({
  params,
}: {
  params: Promise<{ fundId: string }>;
}) {
  const { fundId } = use(params);
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [showGrant, setShowGrant] = useState(false);
  const [userType, setUserType] = useState("user");
  const [userId, setUserId] = useState("");
  const [relation, setRelation] = useState("viewer");

  const { data: grants, isLoading } = useQuery({
    queryKey: ["admin", "funds", fundId, "access"],
    queryFn: () =>
      apiFetch<FundAccessGrant[]>(`admin/funds/${fundId}/access`),
  });

  const grouped = useMemo(() => {
    if (!grants) return [];
    const map = new Map<string, GroupedAccess>();
    for (const g of grants) {
      const key = `${g.user_type}:${g.user_id}`;
      const existing = map.get(key);
      if (existing) {
        if (g.relation_type === "permission") {
          existing.directPermissions.add(g.relation);
        } else {
          existing.roles.add(g.relation);
        }
      } else {
        const entry: GroupedAccess = {
          user_type: g.user_type,
          user_id: g.user_id,
          display_name: g.display_name,
          roles: new Set(),
          directPermissions: new Set(),
        };
        if (g.relation_type === "permission") {
          entry.directPermissions.add(g.relation);
        } else {
          entry.roles.add(g.relation);
        }
        map.set(key, entry);
      }
    }
    return Array.from(map.values());
  }, [grants]);

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["admin", "funds", fundId, "access"],
    });

  const grantAccess = useMutation({
    mutationFn: (body: {
      user_type: string;
      user_id: string;
      relation: string;
    }) =>
      apiFetch(`admin/funds/${fundId}/access`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      invalidate();
      toast.success("Access granted");
    },
    onError: (err) => toast.error(err.message),
  });

  const revokeAccess = useMutation({
    mutationFn: (body: {
      user_type: string;
      user_id: string;
      relation: string;
    }) =>
      apiFetch(`admin/funds/${fundId}/access`, {
        method: "DELETE",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      invalidate();
      toast.success("Access revoked");
    },
    onError: (err) => toast.error(err.message),
  });

  const toggleRole = (entry: GroupedAccess, rel: string) => {
    if (!isAdmin) return;
    const body = {
      user_type: entry.user_type,
      user_id: entry.user_id,
      relation: rel,
    };
    if (entry.roles.has(rel)) {
      revokeAccess.mutate(body);
    } else {
      grantAccess.mutate(body);
    }
  };

  const togglePermission = (entry: GroupedAccess, perm: string) => {
    if (!isAdmin) return;
    const body = {
      user_type: entry.user_type,
      user_id: entry.user_id,
      relation: perm,
    };
    if (entry.directPermissions.has(perm)) {
      revokeAccess.mutate(body);
    } else {
      grantAccess.mutate(body);
    }
  };

  const handleGrant = () => {
    grantAccess.mutate(
      { user_type: userType, user_id: userId, relation },
      {
        onSuccess: () => {
          setShowGrant(false);
          setUserId("");
        },
      },
    );
  };

  const availableRelations =
    userType === "user" ? USER_ROLES : OPERATOR_RELATIONS;
  const isPending = grantAccess.isPending || revokeAccess.isPending;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Fund Access</h2>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowGrant(true)}
            className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm bg-[var(--primary)] text-white hover:opacity-90"
          >
            <Plus size={14} /> Add User
          </button>
        )}
      </div>

      {isAdmin && showGrant && (
        <div className="mb-4 rounded-lg border border-[var(--border)] p-4 bg-[var(--muted)]">
          <div className="flex gap-3 items-end">
            <label className="block">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">
                Type
              </span>
              <select
                value={userType}
                onChange={(e) => {
                  setUserType(e.target.value);
                  setRelation(
                    e.target.value === "user" ? "viewer" : "ops_read",
                  );
                }}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              >
                <option value="user">User</option>
                <option value="operator">Operator</option>
              </select>
            </label>
            <label className="block flex-1">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">
                ID
              </span>
              <input
                placeholder="User or operator UUID"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">
                Initial role
              </span>
              <select
                value={relation}
                onChange={(e) => setRelation(e.target.value)}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              >
                {availableRelations.map((r) => (
                  <option key={r} value={r}>
                    {formatRelation(r)}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={handleGrant}
              disabled={grantAccess.isPending || !userId}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              Add
            </button>
            <button
              type="button"
              onClick={() => setShowGrant(false)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : grouped.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          No access grants for this fund.
        </p>
      ) : (
        <div className="space-y-3">
          {grouped.map((entry) => (
            <AccessCard
              key={`${entry.user_type}:${entry.user_id}`}
              entry={entry}
              isAdmin={isAdmin}
              isPending={isPending}
              onToggleRole={(rel) => toggleRole(entry, rel)}
              onTogglePermission={(perm) => togglePermission(entry, perm)}
              onRemoveAll={() => {
                for (const rel of entry.roles) {
                  revokeAccess.mutate({
                    user_type: entry.user_type,
                    user_id: entry.user_id,
                    relation: rel,
                  });
                }
                for (const perm of entry.directPermissions) {
                  revokeAccess.mutate({
                    user_type: entry.user_type,
                    user_id: entry.user_id,
                    relation: perm,
                  });
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
