"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Pencil, Plus } from "lucide-react";
import Link from "next/link";
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
import type { FundDetail, Page } from "@/shared/types";

export default function FundsPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("USD");

  // Edit state
  const [editFund, setEditFund] = useState<FundDetail | null>(null);
  const [editName, setEditName] = useState("");
  const [editStatus, setEditStatus] = useState("active");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "funds", page],
    queryFn: () =>
      apiFetch<Page<FundDetail>>(`admin/funds?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`),
  });

  const createFund = useMutation({
    mutationFn: (body: { slug: string; name: string; base_currency: string }) =>
      apiFetch<FundDetail>("admin/funds", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "funds"] });
      setShowCreate(false);
      setSlug("");
      setName("");
      setCurrency("USD");
      toast.success("Fund created");
    },
    onError: (err) => toast.error(err.message),
  });

  const updateFund = useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; status?: string }) =>
      apiFetch<FundDetail>(`admin/funds/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "funds"] });
      setEditFund(null);
      toast.success("Fund updated");
    },
    onError: (err) => toast.error(err.message),
  });

  const openEdit = (fund: FundDetail) => {
    setEditFund(fund);
    setEditName(fund.name);
    setEditStatus(fund.status);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Funds</h2>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <Plus size={14} /> Create Fund
          </button>
        )}
      </div>

      {isAdmin && showCreate && (
        <div className="mb-4 rounded-lg border border-[var(--border)] p-4 bg-[var(--muted)]">
          <div className="flex gap-3">
            <input
              placeholder="Slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="flex-1 rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
            <input
              placeholder="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
            <input
              placeholder="Currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-20 rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
            <button
              type="button"
              onClick={() => createFund.mutate({ slug, name, base_currency: currency })}
              disabled={createFund.isPending}
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
        <TableSkeleton rows={5} columns={6} />
      ) : isError ? (
        <ErrorState message={error.message} onRetry={refetch} />
      ) : data?.items.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No funds yet"
          description="Create your first fund to get started."
        />
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Slug</th>
                <th className="py-2 font-medium">Currency</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((fund) => (
                <tr key={fund.id} className="border-b border-[var(--border)]">
                  <td className="py-2">{fund.name}</td>
                  <td className="py-2 text-[var(--muted-foreground)]">{fund.slug}</td>
                  <td className="py-2">{fund.base_currency}</td>
                  <td className="py-2">
                    <StatusBadge
                      label={fund.status}
                      variant={fund.status === "active" ? "success" : "warning"}
                    />
                  </td>
                  <td className="py-2 flex items-center gap-3">
                    <Link
                      href={`/funds/${fund.id}`}
                      className="text-[var(--primary)] text-sm hover:underline"
                    >
                      Manage Access
                    </Link>
                    {isAdmin && (
                      <button
                        type="button"
                        onClick={() => openEdit(fund)}
                        className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                        title="Edit fund"
                      >
                        <Pencil size={14} />
                      </button>
                    )}
                  </td>
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
      <EditModal title="Edit Fund" isOpen={editFund !== null} onClose={() => setEditFund(null)}>
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
            <span className="block text-xs text-[var(--muted-foreground)] mb-1">Status</span>
            <select
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value)}
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            >
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="closed">Closed</option>
            </select>
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setEditFund(null)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={updateFund.isPending}
              onClick={() => {
                if (!editFund) return;
                updateFund.mutate({
                  id: editFund.id,
                  name: editName,
                  status: editStatus,
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
