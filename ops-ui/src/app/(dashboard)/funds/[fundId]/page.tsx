"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { use, useMemo, useState } from "react";
import { toast } from "sonner";
import { AccessCard } from "@/shared/components/access-card";
import { apiFetch } from "@/shared/lib/api";
import {
  formatRelation,
  type GroupedAccess,
  OPERATOR_RELATIONS,
  USER_ROLES,
} from "@/shared/lib/permissions";
import { useRole } from "@/shared/lib/use-role";
import type { FundAccessGrant } from "@/shared/types";

export default function FundAccessPage({ params }: { params: Promise<{ fundId: string }> }) {
  const { fundId } = use(params);
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [showGrant, setShowGrant] = useState(false);
  const [userType, setUserType] = useState("user");
  const [userId, setUserId] = useState("");
  const [relation, setRelation] = useState("viewer");

  const { data: grants, isLoading } = useQuery({
    queryKey: ["admin", "funds", fundId, "access"],
    queryFn: () => apiFetch<FundAccessGrant[]>(`admin/funds/${fundId}/access`),
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
    mutationFn: (body: { user_type: string; user_id: string; relation: string }) =>
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
    mutationFn: (body: { user_type: string; user_id: string; relation: string }) =>
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

  const availableRelations = userType === "user" ? USER_ROLES : OPERATOR_RELATIONS;
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
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">Type</span>
              <select
                value={userType}
                onChange={(e) => {
                  setUserType(e.target.value);
                  setRelation(e.target.value === "user" ? "viewer" : "ops_read");
                }}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              >
                <option value="user">User</option>
                <option value="operator">Operator</option>
              </select>
            </label>
            <label className="block flex-1">
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">ID</span>
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
        <p className="text-sm text-[var(--muted-foreground)]">No access grants for this fund.</p>
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
