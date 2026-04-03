"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Shield } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { EditModal } from "@/shared/components/edit-modal";
import { EmptyState } from "@/shared/components/empty-state";
import { ErrorState } from "@/shared/components/error-state";
import { TableSkeleton } from "@/shared/components/loading-skeleton";
import { Pagination } from "@/shared/components/pagination";
import { StatusBadge } from "@/shared/components/status-badge";
import { apiFetch } from "@/shared/lib/api";
import { PAGE_SIZE } from "@/shared/lib/constants";
import { useRole } from "@/shared/lib/use-role";
import type { OperatorInfo, Page } from "@/shared/types";

export default function OperatorsPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("ops_viewer");

  // Edit state
  const [editOp, setEditOp] = useState<OperatorInfo | null>(null);
  const [editName, setEditName] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [editRole, setEditRole] = useState("ops_viewer");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "operators", page],
    queryFn: () =>
      apiFetch<Page<OperatorInfo>>(`admin/operators?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`),
  });

  const createOperator = useMutation({
    mutationFn: (body: { email: string; name: string; platform_role: string }) =>
      apiFetch<OperatorInfo>("admin/operators", {
        method: "POST",
        body: JSON.stringify(body),
      }),
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

  const updateOperator = useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: string;
      name?: string;
      is_active?: boolean;
      platform_role?: string;
    }) =>
      apiFetch<OperatorInfo>(`admin/operators/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "operators"] });
      setEditOp(null);
      toast.success("Operator updated");
    },
    onError: (err) => toast.error(err.message),
  });

  const openEdit = (op: OperatorInfo) => {
    setEditOp(op);
    setEditName(op.name);
    setEditActive(op.is_active);
    setEditRole(op.platform_role ?? "ops_viewer");
  };

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
        <TableSkeleton rows={5} columns={5} />
      ) : isError ? (
        <ErrorState message={error.message} onRetry={refetch} />
      ) : data?.items.length === 0 ? (
        <EmptyState
          icon={Shield}
          title="No operators yet"
          description="Create your first platform operator to get started."
        />
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Email</th>
                <th className="py-2 font-medium">Role</th>
                <th className="py-2 font-medium">Status</th>
                {isAdmin && <th className="py-2 font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data?.items.map((op) => (
                <tr key={op.id} className="border-b border-[var(--border)]">
                  <td className="py-2">{op.name}</td>
                  <td className="py-2 text-[var(--muted-foreground)]">{op.email}</td>
                  <td className="py-2">
                    <StatusBadge label={op.platform_role ?? "none"} variant="neutral" />
                  </td>
                  <td className="py-2">
                    <StatusBadge
                      label={op.is_active ? "Active" : "Inactive"}
                      variant={op.is_active ? "success" : "danger"}
                    />
                  </td>
                  {isAdmin && (
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={() => openEdit(op)}
                        className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                        title="Edit operator"
                      >
                        <Pencil size={14} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {data && (
            <Pagination total={data.total} limit={PAGE_SIZE} page={page} onPageChange={setPage} />
          )}
        </>
      )}

      {/* Edit modal */}
      <EditModal title="Edit Operator" isOpen={editOp !== null} onClose={() => setEditOp(null)}>
        <div className="space-y-3">
          <label className="block">
            <span className="block text-xs text-[var(--muted-foreground)] mb-1">Name</span>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="block text-xs text-[var(--muted-foreground)] mb-1">Platform Role</span>
            <select
              value={editRole}
              onChange={(e) => setEditRole(e.target.value)}
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            >
              <option value="ops_admin">Ops Admin</option>
              <option value="ops_viewer">Ops Viewer</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={editActive}
              onChange={(e) => setEditActive(e.target.checked)}
            />
            <span className="text-sm">Active</span>
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setEditOp(null)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={updateOperator.isPending}
              onClick={() => {
                if (!editOp) return;
                updateOperator.mutate({
                  id: editOp.id,
                  name: editName,
                  is_active: editActive,
                  platform_role: editRole,
                });
              }}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </EditModal>
    </div>
  );
}
