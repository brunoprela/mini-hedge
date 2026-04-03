"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Users } from "lucide-react";
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
import type { Page, UserInfo } from "@/shared/types";

export default function UsersPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");

  // Edit state
  const [editUser, setEditUser] = useState<UserInfo | null>(null);
  const [editName, setEditName] = useState("");
  const [editActive, setEditActive] = useState(true);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "users", page],
    queryFn: () =>
      apiFetch<Page<UserInfo>>(`admin/users?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`),
  });

  const createUser = useMutation({
    mutationFn: (body: { email: string; name: string }) =>
      apiFetch<UserInfo>("admin/users", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setShowCreate(false);
      setEmail("");
      setName("");
      toast.success("User created");
    },
    onError: (err) => toast.error(err.message),
  });

  const updateUser = useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; is_active?: boolean }) =>
      apiFetch<UserInfo>(`admin/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setEditUser(null);
      toast.success("User updated");
    },
    onError: (err) => toast.error(err.message),
  });

  const openEdit = (user: UserInfo) => {
    setEditUser(user);
    setEditName(user.name);
    setEditActive(user.is_active);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Fund Users</h2>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <Plus size={14} /> Create User
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
            <button
              type="button"
              onClick={() => createUser.mutate({ email, name })}
              disabled={createUser.isPending}
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
        <TableSkeleton rows={5} columns={4} />
      ) : isError ? (
        <ErrorState message={error.message} onRetry={refetch} />
      ) : data?.items.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No users yet"
          description="Create your first fund user to get started."
        />
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Email</th>
                <th className="py-2 font-medium">Status</th>
                {isAdmin && <th className="py-2 font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data?.items.map((user) => (
                <tr key={user.id} className="border-b border-[var(--border)]">
                  <td className="py-2">{user.name}</td>
                  <td className="py-2 text-[var(--muted-foreground)]">{user.email}</td>
                  <td className="py-2">
                    <StatusBadge
                      label={user.is_active ? "Active" : "Inactive"}
                      variant={user.is_active ? "success" : "danger"}
                    />
                  </td>
                  {isAdmin && (
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={() => openEdit(user)}
                        className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                        title="Edit user"
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
      <EditModal title="Edit User" isOpen={editUser !== null} onClose={() => setEditUser(null)}>
        <div className="space-y-3">
          <label className="block">
            <span className="block text-xs text-[var(--muted-foreground)] mb-1">Name</span>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
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
              onClick={() => setEditUser(null)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={updateUser.isPending}
              onClick={() => {
                if (!editUser) return;
                updateUser.mutate({
                  id: editUser.id,
                  name: editName,
                  is_active: editActive,
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
