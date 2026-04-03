"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/shared/lib/api";
import { useRole } from "@/shared/lib/use-role";

interface FundDetail {
  id: string;
  slug: string;
  name: string;
  status: string;
  base_currency: string;
}

export default function FundsPage() {
  const { isAdmin } = useRole();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("USD");

  const { data: funds, isLoading } = useQuery({
    queryKey: ["admin", "funds"],
    queryFn: () => apiFetch<FundDetail[]>("admin/funds"),
  });

  const createFund = useMutation({
    mutationFn: (body: { slug: string; name: string; base_currency: string }) =>
      apiFetch<FundDetail>("admin/funds", { method: "POST", body: JSON.stringify(body) }),
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
        <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
      ) : (
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
            {funds?.map((fund) => (
              <tr key={fund.id} className="border-b border-[var(--border)]">
                <td className="py-2">{fund.name}</td>
                <td className="py-2 text-[var(--muted-foreground)]">{fund.slug}</td>
                <td className="py-2">{fund.base_currency}</td>
                <td className="py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      fund.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {fund.status}
                  </span>
                </td>
                <td className="py-2">
                  <Link
                    href={`/funds/${fund.id}`}
                    className="text-[var(--primary)] text-sm hover:underline"
                  >
                    Manage Access
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
