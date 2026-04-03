"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { use, useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/shared/lib/api";
import { useRole } from "@/shared/lib/use-role";

interface FundAccessGrant {
  user_type: string;
  user_id: string;
  relation: string;
  display_name: string | null;
}

const USER_RELATIONS = [
  "admin",
  "portfolio_manager",
  "analyst",
  "risk_manager",
  "compliance",
  "viewer",
];
const OPERATOR_RELATIONS = ["ops_full", "ops_read"];

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

  const grantAccess = useMutation({
    mutationFn: (body: { user_type: string; user_id: string; relation: string }) =>
      apiFetch(`admin/funds/${fundId}/access`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "funds", fundId, "access"] });
      setShowGrant(false);
      setUserId("");
      toast.success("Access granted");
    },
    onError: (err) => toast.error(err.message),
  });

  const revokeAccess = useMutation({
    mutationFn: (body: { user_type: string; user_id: string; relation: string }) =>
      apiFetch(`admin/funds/${fundId}/access`, { method: "DELETE", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "funds", fundId, "access"] });
      toast.success("Access revoked");
    },
    onError: (err) => toast.error(err.message),
  });

  const relations = userType === "user" ? USER_RELATIONS : OPERATOR_RELATIONS;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Fund Access</h2>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowGrant(true)}
            className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <Plus size={14} /> Grant Access
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
              <span className="block text-xs text-[var(--muted-foreground)] mb-1">Relation</span>
              <select
                value={relation}
                onChange={(e) => setRelation(e.target.value)}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              >
                {relations.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => grantAccess.mutate({ user_type: userType, user_id: userId, relation })}
              disabled={grantAccess.isPending || !userId}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              Grant
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
      ) : grants?.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">No access grants for this fund.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
              <th className="py-2 font-medium">Name</th>
              <th className="py-2 font-medium">Type</th>
              <th className="py-2 font-medium">Relation</th>
              {isAdmin && <th className="py-2 font-medium">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {grants?.map((grant) => (
              <tr
                key={`${grant.user_type}-${grant.user_id}-${grant.relation}`}
                className="border-b border-[var(--border)]"
              >
                <td className="py-2">{grant.display_name ?? grant.user_id}</td>
                <td className="py-2">
                  <span className="inline-block rounded-full bg-[var(--muted)] px-2 py-0.5 text-xs">
                    {grant.user_type}
                  </span>
                </td>
                <td className="py-2">
                  <span className="inline-block rounded-full bg-[var(--accent)] px-2 py-0.5 text-xs text-[var(--accent-foreground)]">
                    {grant.relation}
                  </span>
                </td>
                {isAdmin && (
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() =>
                        revokeAccess.mutate({
                          user_type: grant.user_type,
                          user_id: grant.user_id,
                          relation: grant.relation,
                        })
                      }
                      className="text-[var(--destructive)] hover:opacity-70"
                      title="Revoke access"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
