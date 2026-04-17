"use client";

import { FormField, StatusBadge } from "@mini-hedge/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { EditModal } from "@/shared/components/edit-modal";
import { ResourcePage } from "@/shared/components/resource-page";
import { api } from "@/shared/lib/api-client";
import { PAGE_SIZE } from "@/shared/lib/constants";
import { useForm, z, zodResolver } from "@/shared/lib/forms";
import { useRole } from "@/shared/lib/use-role";
import type { UserInfo } from "@/shared/types";

/* ------------------------------------------------------------------ */
/*  Schemas                                                            */
/* ------------------------------------------------------------------ */

const createUserSchema = z.object({
  email: z.string().trim().email("Enter a valid email"),
  name: z.string().trim().min(1, "Name is required"),
});

type CreateUserValues = z.infer<typeof createUserSchema>;

const editUserSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  is_active: z.boolean(),
});

type EditUserValues = z.infer<typeof editUserSchema>;

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function UsersPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState<UserInfo | null>(null);

  const createForm = useForm<CreateUserValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { email: "", name: "" },
  });

  const editForm = useForm<EditUserValues>({
    resolver: zodResolver(editUserSchema),
    defaultValues: { name: "", is_active: true },
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin", "users", page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/users", {
        params: { query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
      });
      if (error) throw error;
      return data;
    },
  });

  const createUser = useMutation({
    mutationFn: async (body: CreateUserValues) => {
      const { data, error } = await api.POST("/api/v1/admin/users", {
        body,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setShowCreate(false);
      createForm.reset();
      toast.success("User created");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateUser = useMutation({
    mutationFn: async ({ id, ...body }: { id: string } & EditUserValues) => {
      const { data, error } = await api.PATCH(
        "/api/v1/admin/users/{user_id}",
        {
          params: { path: { user_id: id } },
          body,
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setEditUser(null);
      toast.success("User updated");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const openEdit = (user: UserInfo) => {
    setEditUser(user);
    editForm.reset({ name: user.name, is_active: user.is_active });
  };

  useEffect(() => {
    if (!showCreate) createForm.reset();
  }, [showCreate, createForm]);

  const onCreate = createForm.handleSubmit((values) => createUser.mutate(values));
  const onEditSubmit = editForm.handleSubmit((values) => {
    if (!editUser) return;
    updateUser.mutate({ id: editUser.id, ...values });
  });

  return (
    <ResourcePage<UserInfo>
      title="Fund Users"
      createLabel="Create User"
      emptyIcon={Users}
      emptyTitle="No users yet"
      emptyDescription="Create your first fund user to get started."
      rows={data?.items}
      total={data?.total}
      limit={PAGE_SIZE}
      page={page}
      onPageChange={setPage}
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message}
      onRetry={refetch}
      rowKey={(u) => u.id}
      columns={[
        { key: "name", header: "Name", render: (u) => u.name },
        {
          key: "email",
          header: "Email",
          render: (u) => (
            <span className="text-[var(--muted-foreground)]">{u.email}</span>
          ),
        },
        {
          key: "status",
          header: "Status",
          render: (u) => (
            <StatusBadge
              label={u.is_active ? "Active" : "Inactive"}
              variant={u.is_active ? "success" : "danger"}
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
          <div className="grid gap-3 sm:grid-cols-2">
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
              disabled={createUser.isPending}
              className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              {createUser.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      }
      editModal={
        <EditModal title="Edit User" isOpen={editUser !== null} onClose={() => setEditUser(null)}>
          <form onSubmit={onEditSubmit} className="space-y-3">
            <FormField label="Name" required error={editForm.formState.errors.name?.message}>
              <input
                className="w-full rounded border border-[var(--border)] px-3 py-1.5 text-sm"
                {...editForm.register("name")}
              />
            </FormField>
            <label className="flex items-center gap-2">
              <input type="checkbox" {...editForm.register("is_active")} />
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
                type="submit"
                disabled={updateUser.isPending}
                className="rounded bg-[var(--primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
              >
                {updateUser.isPending ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        </EditModal>
      }
    />
  );
}
