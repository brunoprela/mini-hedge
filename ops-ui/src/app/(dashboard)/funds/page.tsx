"use client";

import { FormField } from "@mini-hedge/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { EditModal } from "@/shared/components/edit-modal";
import { EmptyState } from "@mini-hedge/ui";
import { ErrorState } from "@mini-hedge/ui";
import { TableSkeleton } from "@mini-hedge/ui";
import { Pagination } from "@mini-hedge/ui";
import { StatusBadge } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";
import { PAGE_SIZE } from "@/shared/lib/constants";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { useRole } from "@/shared/lib/use-role";
import type { FundDetail } from "@/shared/types";
import type { components } from "@mini-hedge/api-types";

type BaseCurrency = components["schemas"]["CreateFundRequest"]["base_currency"];

/* ------------------------------------------------------------------ */
/*  Schemas                                                            */
/* ------------------------------------------------------------------ */

// BaseCurrency may be a union of strings; use string + regex + cast on submit.
const createFundSchema = z.object({
  slug: z
    .string()
    .trim()
    .min(1, "Slug is required")
    .regex(/^[a-z0-9-]+$/, "Slug must be lowercase letters, numbers, and hyphens"),
  name: z.string().trim().min(1, "Name is required"),
  base_currency: z
    .string()
    .trim()
    .min(3, "Currency is required")
    .regex(/^[A-Z]{3}$/, "Use a 3-letter currency code (e.g. USD)"),
});

type CreateFundValues = z.infer<typeof createFundSchema>;

const editFundSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  status: z.enum(["active", "suspended", "closed"]),
});

type EditFundValues = z.infer<typeof editFundSchema>;

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function FundsPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [editFund, setEditFund] = useState<FundDetail | null>(null);

  const createForm = useForm<CreateFundValues>({
    resolver: zodResolver(createFundSchema),
    defaultValues: { slug: "", name: "", base_currency: "USD" },
  });

  const editForm = useForm<EditFundValues>({
    resolver: zodResolver(editFundSchema),
    defaultValues: { name: "", status: "active" },
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "funds", page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/funds", {
        params: { query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
      });
      if (error) throw error;
      return data;
    },
  });

  const createFund = useMutation({
    mutationFn: async (values: CreateFundValues) => {
      const { data, error } = await api.POST("/api/v1/admin/funds", {
        body: {
          slug: values.slug,
          name: values.name,
          base_currency: values.base_currency as BaseCurrency,
        },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "funds"] });
      setShowCreate(false);
      createForm.reset();
      toast.success("Fund created");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateFund = useMutation({
    mutationFn: async ({
      id,
      ...body
    }: { id: string } & EditFundValues) => {
      const { data, error } = await api.PATCH(
        "/api/v1/admin/funds/{fund_id}",
        {
          params: { path: { fund_id: id } },
          body,
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "funds"] });
      setEditFund(null);
      toast.success("Fund updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const openEdit = (fund: FundDetail) => {
    setEditFund(fund);
    editForm.reset({
      name: fund.name,
      status: (fund.status as EditFundValues["status"]) ?? "active",
    });
  };

  useEffect(() => {
    if (!showCreate) createForm.reset();
  }, [showCreate, createForm]);

  const onCreate = createForm.handleSubmit((values) => createFund.mutate(values));
  const onEdit = editForm.handleSubmit((values) => {
    if (!editFund) return;
    updateFund.mutate({ id: editFund.id, ...values });
  });

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
        <form
          onSubmit={onCreate}
          className="mb-4 rounded-lg border border-[var(--border)] p-4 bg-[var(--muted)] space-y-3"
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField
              label="Slug"
              required
              error={createForm.formState.errors.slug?.message}
            >
              <input
                placeholder="Slug"
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
                {...createForm.register("slug")}
              />
            </FormField>
            <FormField
              label="Name"
              required
              error={createForm.formState.errors.name?.message}
            >
              <input
                placeholder="Name"
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
                {...createForm.register("name")}
              />
            </FormField>
            <FormField
              label="Currency"
              required
              error={createForm.formState.errors.base_currency?.message}
            >
              <input
                placeholder="USD"
                maxLength={3}
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm uppercase"
                {...createForm.register("base_currency")}
              />
            </FormField>
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createFund.isPending}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {createFund.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
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
        <form onSubmit={onEdit} className="space-y-3">
          <FormField label="Name" required error={editForm.formState.errors.name?.message}>
            <input
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              {...editForm.register("name")}
            />
          </FormField>
          <FormField label="Status" required error={editForm.formState.errors.status?.message}>
            <select
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              {...editForm.register("status")}
            >
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="closed">Closed</option>
            </select>
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setEditFund(null)}
              className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={updateFund.isPending}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {updateFund.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </EditModal>
    </div>
  );
}
