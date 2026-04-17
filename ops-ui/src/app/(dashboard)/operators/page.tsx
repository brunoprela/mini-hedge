"use client";

import { FormField } from "@mini-hedge/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Shield } from "lucide-react";
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
import type { OperatorInfo } from "@/shared/types";

/* ------------------------------------------------------------------ */
/*  Schemas                                                            */
/* ------------------------------------------------------------------ */

const PLATFORM_ROLES = ["ops_admin", "ops_viewer"] as const;

const createOperatorSchema = z.object({
  email: z.string().trim().email("Enter a valid email"),
  name: z.string().trim().min(1, "Name is required"),
  platform_role: z.enum(PLATFORM_ROLES),
});

type CreateOperatorValues = z.infer<typeof createOperatorSchema>;

const editOperatorSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  platform_role: z.enum(PLATFORM_ROLES),
  is_active: z.boolean(),
});

type EditOperatorValues = z.infer<typeof editOperatorSchema>;

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function OperatorsPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [editOp, setEditOp] = useState<OperatorInfo | null>(null);

  const createForm = useForm<CreateOperatorValues>({
    resolver: zodResolver(createOperatorSchema),
    defaultValues: { email: "", name: "", platform_role: "ops_viewer" },
  });

  const editForm = useForm<EditOperatorValues>({
    resolver: zodResolver(editOperatorSchema),
    defaultValues: { name: "", platform_role: "ops_viewer", is_active: true },
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "operators", page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/operators", {
        params: { query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
      });
      if (error) throw error;
      return data;
    },
  });

  const createOperator = useMutation({
    mutationFn: async (body: CreateOperatorValues) => {
      const { data, error } = await api.POST("/api/v1/admin/operators", {
        body,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "operators"] });
      setShowCreate(false);
      createForm.reset();
      toast.success("Operator created");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateOperator = useMutation({
    mutationFn: async ({ id, ...body }: { id: string } & EditOperatorValues) => {
      const { data, error } = await api.PATCH(
        "/api/v1/admin/operators/{operator_id}",
        {
          params: { path: { operator_id: id } },
          body,
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "operators"] });
      setEditOp(null);
      toast.success("Operator updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const openEdit = (op: OperatorInfo) => {
    setEditOp(op);
    editForm.reset({
      name: op.name,
      platform_role: (op.platform_role as EditOperatorValues["platform_role"]) ?? "ops_viewer",
      is_active: op.is_active,
    });
  };

  useEffect(() => {
    if (!showCreate) createForm.reset();
  }, [showCreate, createForm]);

  const onCreate = createForm.handleSubmit((values) => createOperator.mutate(values));
  const onEdit = editForm.handleSubmit((values) => {
    if (!editOp) return;
    updateOperator.mutate({ id: editOp.id, ...values });
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
        <form
          onSubmit={onCreate}
          className="mb-4 rounded-lg border border-[var(--border)] p-4 bg-[var(--muted)] space-y-3"
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField
              label="Email"
              required
              error={createForm.formState.errors.email?.message}
            >
              <input
                placeholder="user@example.com"
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
                {...createForm.register("email")}
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
              label="Role"
              required
              error={createForm.formState.errors.platform_role?.message}
            >
              <select
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
                {...createForm.register("platform_role")}
              >
                <option value="ops_admin">Ops Admin</option>
                <option value="ops_viewer">Ops Viewer</option>
              </select>
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
              disabled={createOperator.isPending}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {createOperator.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
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
        <form onSubmit={onEdit} className="space-y-3">
          <FormField label="Name" required error={editForm.formState.errors.name?.message}>
            <input
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              {...editForm.register("name")}
            />
          </FormField>
          <FormField
            label="Platform Role"
            required
            error={editForm.formState.errors.platform_role?.message}
          >
            <select
              className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
              {...editForm.register("platform_role")}
            >
              <option value="ops_admin">Ops Admin</option>
              <option value="ops_viewer">Ops Viewer</option>
            </select>
          </FormField>
          <label className="flex items-center gap-2">
            <input type="checkbox" {...editForm.register("is_active")} />
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
              type="submit"
              disabled={updateOperator.isPending}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {updateOperator.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </EditModal>
    </div>
  );
}
