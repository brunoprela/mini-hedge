"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/shared/lib/api";
import { useRole } from "@/shared/lib/use-role";

interface OperatorInfo {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  platform_role: string | null;
}

export default function OperatorsPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("ops_viewer");

  const { data: operators, isLoading } = useQuery({
    queryKey: ["admin", "operators"],
    queryFn: () => apiFetch<OperatorInfo[]>("admin/operators"),
  });

  const createOperator = useMutation({
    mutationFn: (body: { email: string; name: string; platform_role: string }) =>
      apiFetch<OperatorInfo>("admin/operators", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "operators"] });
      setShowCreate(false);
      setEmail("");
      setName("");
      setRole("ops_viewer");
      toast.success("Operator created");
    },
    onError: (err) => toast.error(err.message),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Operators</h2>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <Plus size={14} /> Create Operator
          </button>
        )}
      </div>

      {isAdmin && showCreate && (
        <div className="mb-4 rounded-lg border border-[var(--border)] p-4 bg-[var(--muted)]">
          <div className="flex gap-3">
            <input
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
            <input
              placeholder="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            >
              <option value="ops_admin">Ops Admin</option>
              <option value="ops_viewer">Ops Viewer</option>
            </select>
            <button
              type="button"
              onClick={() => createOperator.mutate({ email, name, platform_role: role })}
              disabled={createOperator.isPending}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
              <th className="py-2 font-medium">Name</th>
              <th className="py-2 font-medium">Email</th>
              <th className="py-2 font-medium">Role</th>
              <th className="py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {operators?.map((op) => (
              <tr key={op.id} className="border-b border-[var(--border)]">
                <td className="py-2">{op.name}</td>
                <td className="py-2 text-[var(--muted-foreground)]">{op.email}</td>
                <td className="py-2">
                  <span className="inline-block rounded-full bg-[var(--accent)] px-2 py-0.5 text-xs text-[var(--accent-foreground)]">
                    {op.platform_role ?? "none"}
                  </span>
                </td>
                <td className="py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      op.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                    }`}
                  >
                    {op.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
