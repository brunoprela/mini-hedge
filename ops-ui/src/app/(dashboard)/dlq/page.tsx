"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { apiFetch } from "@/shared/lib/api";

interface DLQTopic {
  topic: string;
  count: number;
}

interface DLQMessage {
  id: string;
  topic: string;
  payload: Record<string, unknown>;
  error: string;
  created_at: string;
}

export default function DLQPage() {
  const queryClient = useQueryClient();
  const [peekedTopic, setPeekedTopic] = useState<string | null>(null);

  const { data: topics, isLoading: topicsLoading } = useQuery({
    queryKey: ["dlq", "topics"],
    queryFn: () => apiFetch<DLQTopic[]>("admin/dlq"),
  });

  const {
    data: messages,
    isLoading: messagesLoading,
    refetch: refetchMessages,
  } = useQuery({
    queryKey: ["dlq", "messages", peekedTopic],
    queryFn: () => apiFetch<DLQMessage[]>(`admin/dlq/${peekedTopic}`),
    enabled: !!peekedTopic,
  });

  const replay = useMutation({
    mutationFn: (topic: string) =>
      apiFetch(`admin/dlq/${topic}/replay`, { method: "POST" }),
    onSuccess: (_data, topic) => {
      queryClient.invalidateQueries({ queryKey: ["dlq", "topics"] });
      queryClient.invalidateQueries({ queryKey: ["dlq", "messages", topic] });
      toast.success(`Replayed messages for ${topic}`);
    },
    onError: (err) => toast.error(err.message),
  });

  const handlePeek = (topic: string) => {
    setPeekedTopic(topic);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-[var(--foreground)]">Dead Letter Queue</h1>

      {/* Topics table */}
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full divide-y divide-[var(--border)]">
          <thead className="bg-[var(--card)]">
            <tr>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Topic</th>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Message Count</th>
              <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--table-border)]">
            {topicsLoading && (
              <tr>
                <td colSpan={3} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">Loading...</td>
              </tr>
            )}
            {!topicsLoading && (!topics || topics.length === 0) && (
              <tr>
                <td colSpan={3} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">No dead-letter topics</td>
              </tr>
            )}
            {topics?.map((t) => (
              <tr key={t.topic} className="transition-colors hover:bg-[var(--table-row-hover)]">
                <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]">{t.topic}</td>
                <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]">{t.count}</td>
                <td className="px-3 py-2 flex gap-2">
                  <button
                    onClick={() => handlePeek(t.topic)}
                    className="inline-flex items-center gap-1 rounded bg-[var(--muted)] px-2 py-1 text-xs font-medium text-[var(--foreground)] hover:opacity-80"
                  >
                    <Eye size={12} /> Peek
                  </button>
                  <button
                    onClick={() => replay.mutate(t.topic)}
                    disabled={replay.isPending}
                    className="inline-flex items-center gap-1 rounded bg-[var(--primary)] px-2 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                  >
                    <RotateCcw size={12} /> Replay
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Peeked messages detail */}
      {peekedTopic && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-[var(--foreground)]">
            Messages in <span className="font-mono">{peekedTopic}</span>
          </h2>
          <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead className="bg-[var(--card)]">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">ID</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Error</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Created At</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {messagesLoading && (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">Loading...</td>
                  </tr>
                )}
                {!messagesLoading && (!messages || messages.length === 0) && (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-sm text-[var(--muted-foreground)]">No messages</td>
                  </tr>
                )}
                {messages?.map((m) => (
                  <tr key={m.id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm font-mono text-[var(--foreground)]" title={m.id}>
                      {m.id.slice(0, 8)}...
                    </td>
                    <td className="px-3 py-2 text-sm text-red-600 max-w-xs truncate" title={m.error}>
                      {m.error}
                    </td>
                    <td className="px-3 py-2 text-sm font-mono text-[var(--muted-foreground)] whitespace-nowrap">
                      {new Date(m.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <pre className="max-h-24 max-w-md overflow-auto rounded bg-[var(--muted)] p-2 text-[11px] font-mono text-[var(--foreground)]">
                        {JSON.stringify(m.payload, null, 2)}
                      </pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
