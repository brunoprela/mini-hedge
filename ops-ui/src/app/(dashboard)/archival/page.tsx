"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive } from "lucide-react";
import { toast } from "sonner";
import { LoadingSkeleton } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";

interface ArchivedMonth {
  fund_slug: string;
  year: number;
  month: number;
  event_count: number;
  archived_at: string;
}

export default function ArchivalPage() {
  const queryClient = useQueryClient();

  const { data: archives, isLoading } = useQuery({
    queryKey: ["archival"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/archival");
      if (error) throw error;
      return data as unknown as ArchivedMonth[];
    },
  });

  const runFull = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/admin/archival/run");
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archival"] });
      toast.success("Full archival triggered");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const archiveMonth = useMutation({
    mutationFn: async (row: ArchivedMonth) => {
      const { data, error } = await api.POST(
        "/api/v1/admin/archival/{fund_slug}/{year}/{month}",
        {
          params: {
            path: {
              fund_slug: row.fund_slug,
              year: row.year,
              month: row.month,
            },
          },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archival"] });
      toast.success("Month archived");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-[var(--foreground)]">Audit Archival</h1>

      {/* Action bar */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => runFull.mutate()}
          disabled={runFull.isPending}
          className="inline-flex items-center gap-1.5 rounded bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          <Archive size={14} />
          Run Full Archival
        </button>
      </div>

      {/* Archive history table */}
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full divide-y divide-[var(--border)]">
          <thead className="bg-[var(--card)]">
            <tr>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Fund</th>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Year</th>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Month</th>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Event Count</th>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Archived At</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-3 py-4">
                  <LoadingSkeleton variant="table-row" rows={4} columns={5} />
                </td>
              </tr>
            )}
            {!isLoading && (!archives || archives.length === 0) && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">No archived months</td>
              </tr>
            )}
            {archives?.map((a) => (
              <tr key={`${a.fund_slug}-${a.year}-${a.month}`} className="transition-colors hover:bg-[var(--table-row-hover)]">
                <td className="px-3 py-2 text-sm font-medium text-[var(--foreground)]">{a.fund_slug}</td>
                <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]">{a.year}</td>
                <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]">{a.month}</td>
                <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]">{a.event_count.toLocaleString()}</td>
                <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)]">
                  {new Date(a.archived_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
