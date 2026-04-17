"use client";

import { FormField, StatusBadge } from "@mini-hedge/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { EditModal } from "@/shared/components/edit-modal";
import { ResourcePage } from "@/shared/components/resource-page";
import { api } from "@/shared/lib/api-client";
import { PAGE_SIZE } from "@/shared/lib/constants";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { useRole } from "@/shared/lib/use-role";
import type { CustomerInfo } from "@/shared/types";

const CUSTOMER_TYPES = [
  { value: "direct_fund", label: "Direct Fund" },
  { value: "fund_administrator", label: "Fund Administrator" },
] as const;

function customerTypeLabel(t: string) {
  return CUSTOMER_TYPES.find((ct) => ct.value === t)?.label ?? t;
}

/* ------------------------------------------------------------------ */
/*  Schemas                                                            */
/* ------------------------------------------------------------------ */

const createCustomerSchema = z.object({
  slug: z
    .string()
    .trim()
    .min(1, "Slug is required")
    .regex(/^[a-z0-9-]+$/, "Slug must be lowercase letters, numbers, and hyphens"),
  name: z.string().trim().min(1, "Name is required"),
  customer_type: z.enum(["direct_fund", "fund_administrator"]),
});

type CreateCustomerValues = z.infer<typeof createCustomerSchema>;

const editCustomerSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  status: z.enum(["active", "inactive", "offboarded"]),
});

type EditCustomerValues = z.infer<typeof editCustomerSchema>;

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function CustomersPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [editCustomer, setEditCustomer] = useState<CustomerInfo | null>(null);

  const createForm = useForm<CreateCustomerValues>({
    resolver: zodResolver(createCustomerSchema),
    defaultValues: { slug: "", name: "", customer_type: "direct_fund" },
  });

  const editForm = useForm<EditCustomerValues>({
    resolver: zodResolver(editCustomerSchema),
    defaultValues: { name: "", status: "active" },
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "customers", page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/customers", {
        params: { query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
      });
      if (error) throw error;
      return data;
    },
  });

  // Optimistic create: prepend a provisional customer row so the list updates
  // immediately; rollback if the server errors.
  const createCustomer = useMutation({
    mutationFn: async (body: CreateCustomerValues) => {
      const { data, error } = await api.POST("/api/v1/admin/customers", {
        body,
      });
      if (error) throw error;
      return data;
    },
    onMutate: async (newCustomer) => {
      const queryKey = ["admin", "customers", page];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<{
        items: CustomerInfo[];
        total: number;
      }>(queryKey);
      const optimistic: CustomerInfo = {
        id: `temp-${Date.now()}`,
        slug: newCustomer.slug,
        name: newCustomer.name,
        customer_type: newCustomer.customer_type,
        status: "active",
      } as CustomerInfo;
      queryClient.setQueryData<
        { items: CustomerInfo[]; total: number } | undefined
      >(queryKey, (old) =>
        old
          ? { ...old, items: [optimistic, ...old.items], total: old.total + 1 }
          : { items: [optimistic], total: 1 },
      );
      return { previous, queryKey };
    },
    onSuccess: () => {
      setShowCreate(false);
      createForm.reset();
      toast.success("Customer created");
    },
    onError: (err: Error, _vars, context) => {
      if (context?.previous && context.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
      toast.error(err.message);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "customers"] });
    },
  });

  const updateCustomer = useMutation({
    mutationFn: async ({
      id,
      ...body
    }: { id: string } & EditCustomerValues) => {
      const { data, error } = await api.PATCH(
        "/api/v1/admin/customers/{customer_id}",
        {
          params: { path: { customer_id: id } },
          body,
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "customers"] });
      setEditCustomer(null);
      toast.success("Customer updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const openEdit = (customer: CustomerInfo) => {
    setEditCustomer(customer);
    editForm.reset({
      name: customer.name,
      status: (customer.status as EditCustomerValues["status"]) ?? "active",
    });
  };

  // Reset create form when the panel is hidden so errors clear
  useEffect(() => {
    if (!showCreate) createForm.reset();
  }, [showCreate, createForm]);

  const onCreate = createForm.handleSubmit((values) => createCustomer.mutate(values));
  const onEditSubmit = editForm.handleSubmit((values) => {
    if (!editCustomer) return;
    updateCustomer.mutate({ id: editCustomer.id, ...values });
  });

  return (
    <ResourcePage<CustomerInfo>
      title="Customers"
      createLabel="Create Customer"
      emptyIcon={Building2}
      emptyTitle="No customers yet"
      emptyDescription="Create your first customer to get started."
      rows={data?.items}
      total={data?.total}
      limit={PAGE_SIZE}
      page={page}
      onPageChange={setPage}
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message}
      onRetry={refetch}
      rowKey={(c) => c.id}
      columns={[
        { key: "name", header: "Name", render: (c) => c.name },
        {
          key: "slug",
          header: "Slug",
          render: (c) => (
            <span className="text-[var(--muted-foreground)]">{c.slug}</span>
          ),
        },
        {
          key: "type",
          header: "Type",
          render: (c) => customerTypeLabel(c.customer_type),
        },
        {
          key: "status",
          header: "Status",
          render: (c) => (
            <StatusBadge
              label={c.status}
              variant={c.status === "active" ? "success" : "danger"}
            />
          ),
        },
      ]}
      canCreate={isAdmin}
      canEdit={isAdmin}
      showCreate={showCreate}
      onOpenCreate={() => setShowCreate(true)}
      onEdit={openEdit}
      createForm={
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
                placeholder="e.g. acme-capital"
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
              label="Type"
              required
              error={createForm.formState.errors.customer_type?.message}
            >
              <select
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
                {...createForm.register("customer_type")}
              >
                {CUSTOMER_TYPES.map((ct) => (
                  <option key={ct.value} value={ct.value}>
                    {ct.label}
                  </option>
                ))}
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
              disabled={createCustomer.isPending}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {createCustomer.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      }
      editModal={
        <EditModal
          title="Edit Customer"
          isOpen={editCustomer !== null}
          onClose={() => setEditCustomer(null)}
        >
          <form onSubmit={onEditSubmit} className="space-y-3">
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
                <option value="inactive">Inactive</option>
                <option value="offboarded">Offboarded</option>
              </select>
            </FormField>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setEditCustomer(null)}
                className="rounded border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateCustomer.isPending}
                className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
              >
                {updateCustomer.isPending ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        </EditModal>
      }
    />
  );
}
