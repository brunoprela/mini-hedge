"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { usePermission } from "@/shared/hooks/use-permission";
import { clientFetch } from "@/shared/lib/api";
import { Permission } from "@/shared/lib/permissions";
import { violationsQueryOptions } from "../api";
import type { Violation } from "../types";

const SEVERITY_BADGE: Record<string, string> = {
  block: "bg-red-100 text-red-800",
  warning: "bg-yellow-100 text-yellow-800",
  breach: "bg-orange-100 text-orange-800",
};

export function ViolationsPanel({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { can } = usePermission();
  const queryClient = useQueryClient();
  const { data: violations, isLoading } = useQuery(violationsQueryOptions(fundSlug, portfolioId));

  const canWrite = can(Permission.COMPLIANCE_WRITE);

  const resolveMutation = useMutation({
    mutationFn: (violationId: string) =>
      clientFetch<Violation>(`/compliance/violations/${violationId}/resolve`, {
        fundSlug,
        method: "POST",
        body: { resolved_by: "current_user" },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations"] });
      toast.success("Violation resolved");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading violations...</p>;
  }

  if (!violations || violations.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">No active violations.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">Rule</th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Severity
            </th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Message
            </th>
            <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
              Detected
            </th>
            {canWrite && (
              <th className="px-4 py-3 text-left font-medium text-[var(--muted-foreground)]">
                Actions
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {violations.map((v) => (
            <tr key={v.id} className="border-b border-[var(--border)] last:border-b-0">
              <td className="px-4 py-3 font-medium">{v.rule_name}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_BADGE[v.severity] ?? ""}`}
                >
                  {v.severity}
                </span>
              </td>
              <td className="px-4 py-3 text-[var(--muted-foreground)]">{v.message}</td>
              <td className="px-4 py-3 text-xs text-[var(--muted-foreground)]">
                {new Date(v.detected_at).toLocaleString()}
              </td>
              {canWrite && (
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => resolveMutation.mutate(v.id)}
                    disabled={resolveMutation.isPending}
                    className="text-sm text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
                  >
                    Resolve
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
