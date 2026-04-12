"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Pencil, Plus } from "lucide-react";
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
import type { CustomerInfo, Page } from "@/shared/types";

const CUSTOMER_TYPES = [
  { value: "direct_fund", label: "Direct Fund" },
  { value: "fund_administrator", label: "Fund Administrator" },
];

function customerTypeLabel(t: string) {
  return CUSTOMER_TYPES.find((ct) => ct.value === t)?.label ?? t;
}

export default function CustomersPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [customerType, setCustomerType] = useState("direct_fund");

  // Edit state
  const [editCustomer, setEditCustomer] = useState<CustomerInfo | null>(null);
  const [editName, setEditName] = useState("");
  const [editStatus, setEditStatus] = useState("active");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "customers", page],
    queryFn: () =>
      apiFetch<Page<CustomerInfo>>(
        `admin/customers?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
      ),
  });

  const createCustomer = useMutation({
    mutationFn: (body: { slug: string; name: string; customer_type: string }) =>
      apiFetch<CustomerInfo>("admin/customers", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "customers"] });
      setShowCreate(false);
      setSlug("");
      setName("");
      setCustomerType("direct_fund");
      toast.success("Customer created");
    },
    onError: (err) => toast.error(err.message),
  });

  const updateCustomer = useMutation({
    mutationFn: ({
      id,
      ...body
    }: { id: string; name?: string; status?: string }) =>
      apiFetch<CustomerInfo>(`admin/customers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "customers"] });
      setEditCustomer(null);
      toast.success("Customer updated");
    },
    onError: (err) => toast.error(err.message),
  });

  const openEdit = (customer: CustomerInfo) => {
    setEditCustomer(customer);
    setEditName(customer.name);
    setEditStatus(customer.status);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Customers</h2>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <Plus size={14} /> Create Customer
          </button>
        )}
      </div>

      {isAdmin && showCreate && (
        <div className="mb-4 rounded-lg border border-[var(--border)] p-4 bg-[var(--muted)]">
          <div className="flex gap-3">
            <input
              placeholder="Slug (e.g. acme-capital)"
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
            <select
              value={customerType}
              onChange={(e) => setCustomerType(e.target.value)}
              className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            >
              {CUSTOMER_TYPES.map((ct) => (
                <option key={ct.value} value={ct.value}>
                  {ct.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() =>
                createCustomer.mutate({
                  slug,
                  name,
                  customer_type: customerType,
                })
              }
              disabled={createCustomer.isPending}
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
          icon={Building2}
          title="No customers yet"
          description="Create your first customer to get started."
        />
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">Slug</th>
                <th className="py-2 font-medium">Type</th>
                <th className="py-2 font-medium">Status</th>
                {isAdmin && <th className="py-2 font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data?.items.map((customer) => (
                <tr
                  key={customer.id}
                  className="border-b border-[var(--border)]"
                >
                  <td className="py-2">{customer.name}</td>
                  <td className="py-2 text-[var(--muted-foreground)]">
                    {customer.slug}
                  </td>
                  <td className="py-2">
                    {customerTypeLabel(customer.customer_type)}
                  </td>
                  <td className="py-2">
                    <StatusBadge
                      label={customer.status}
                      variant={
                        customer.status === "active" ? "success" : "danger"
                      }
                    />
                  </td>
                  {isAdmin && (
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={() => openEdit(customer)}
                        className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                        title="Edit customer"
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
            <Pagination
              total={data.total}
              limit={PAGE_SIZE}
              page={page}
              onPageChange={setPage}
            />
          )}
        </>
      )}

      {/* Edit modal */}
      <EditModal
        title="Edit Customer"
        isOpen={editCustomer !== null}
        onClose={() => setEditCustomer(null)}
      >
        <div className="space-y-3">
          <label className="block">
            <span className="block text-xs text-[var(--muted-foreground)] mb-1">
              Name
            </span>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="block text-xs text-[var(--muted-foreground)] mb-1">
              Status
            </span>
            <select
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value)}
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="offboarded">Offboarded</option>
            </select>
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setEditCustomer(null)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={updateCustomer.isPending}
              onClick={() => {
                if (!editCustomer) return;
                updateCustomer.mutate({
                  id: editCustomer.id,
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
