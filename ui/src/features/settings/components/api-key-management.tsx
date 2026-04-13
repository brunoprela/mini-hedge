"use client";

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { SectionPanel } from "@/shared/components/section-panel";
import { apiKeysQueryOptions, createApiKey, revokeApiKey } from "../api";
import type { ApiKey } from "../types";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatDate(iso: string | null) {
  if (!iso) return "Never";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/* ------------------------------------------------------------------ */
/*  Generate key form                                                  */
/* ------------------------------------------------------------------ */

function GenerateKeyForm({
  onGenerate,
  onCancel,
  isPending,
}: {
  onGenerate: (name: string) => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");

  return (
    <div className="space-y-3 border-t border-[var(--border)] p-4">
      <p className="text-xs font-medium text-[var(--foreground)]">Generate New API Key</p>
      <div className="flex flex-col gap-2">
        <input
          type="text"
          placeholder="Key name (e.g. production-bot)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm placeholder:text-[var(--muted-foreground)]"
        />
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!name.trim() || isPending}
          onClick={() => onGenerate(name.trim())}
          className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:opacity-90 disabled:opacity-40"
        >
          {isPending ? "Generating..." : "Generate"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Newly created key banner                                           */
/* ------------------------------------------------------------------ */

function NewKeyBanner({ fullKey, onDismiss }: { fullKey: string; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async () => {
    await navigator.clipboard.writeText(fullKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [fullKey]);

  return (
    <div className="border-t border-[var(--border)] bg-[var(--card)] p-4">
      <div className="rounded-md border border-yellow-500/40 bg-yellow-500/10 p-3">
        <p className="mb-2 text-xs font-semibold text-yellow-400">
          This will only be shown once. Copy it now.
        </p>
        <div className="flex items-center gap-2">
          <code className="flex-1 overflow-x-auto rounded bg-[var(--background)] px-2 py-1 font-mono text-xs text-[var(--foreground)]">
            {fullKey}
          </code>
          <button
            type="button"
            onClick={copy}
            className="shrink-0 rounded-md border border-[var(--border)] px-2 py-1 text-xs font-medium transition-colors hover:bg-[var(--accent)]"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="mt-2 text-[11px] text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
      >
        I have saved the key
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Revoke confirmation                                                */
/* ------------------------------------------------------------------ */

function RevokeConfirm({
  keyName,
  onConfirm,
  onCancel,
  isPending,
}: {
  keyName: string;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] text-[var(--muted-foreground)]">
        Revoke <strong>{keyName}</strong>?
      </span>
      <button
        type="button"
        onClick={onConfirm}
        disabled={isPending}
        className="rounded px-2 py-0.5 text-[11px] font-medium text-[var(--destructive)] transition-colors hover:bg-[var(--destructive)]/10 disabled:opacity-40"
      >
        {isPending ? "Revoking..." : "Confirm"}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="rounded px-2 py-0.5 text-[11px] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        Cancel
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Key table row                                                      */
/* ------------------------------------------------------------------ */

function KeyRow({
  apiKey,
  fundSlug,
}: {
  apiKey: ApiKey;
  fundSlug: string;
}) {
  const queryClient = useQueryClient();
  const [confirmingRevoke, setConfirmingRevoke] = useState(false);

  const revokeMutation = useMutation({
    mutationFn: () => revokeApiKey(fundSlug, apiKey.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys", fundSlug] });
      setConfirmingRevoke(false);
    },
  });

  return (
    <tr className="border-b border-[var(--border)] last:border-b-0">
      <td className="px-3 py-2 text-sm">{apiKey.name}</td>
      <td className="px-3 py-2 font-mono text-xs text-[var(--muted-foreground)]">
        {apiKey.key_hint}
      </td>
      <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
        {formatDate(apiKey.created_at)}
      </td>
      <td className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
        {formatDate(apiKey.last_used_at)}
      </td>
      <td className="px-3 py-2">
        {confirmingRevoke ? (
          <RevokeConfirm
            keyName={apiKey.name}
            onConfirm={() => revokeMutation.mutate()}
            onCancel={() => setConfirmingRevoke(false)}
            isPending={revokeMutation.isPending}
          />
        ) : (
          <button
            type="button"
            onClick={() => setConfirmingRevoke(true)}
            className="rounded px-2 py-0.5 text-[11px] font-medium text-[var(--destructive)] transition-colors hover:bg-[var(--destructive)]/10"
          >
            Revoke
          </button>
        )}
      </td>
    </tr>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export function ApiKeyManagement() {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [showForm, setShowForm] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);

  const { data: keys = [], isLoading, isError } = useQuery(apiKeysQueryOptions(fundSlug));

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; scopes: string[] }) =>
      createApiKey(fundSlug, payload),
    onSuccess: (response) => {
      setNewlyCreatedKey(response.key);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["api-keys", fundSlug] });
    },
  });

  return (
    <SectionPanel
      title="API Keys"
      actions={
        !showForm && !newlyCreatedKey ? (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="rounded px-2 py-0.5 text-[11px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--accent)]"
          >
            + Generate New Key
          </button>
        ) : undefined
      }
    >
      {/* Table */}
      {isLoading ? (
        <div className="px-3 py-6 text-center text-xs text-[var(--muted-foreground)]">
          Loading API keys...
        </div>
      ) : isError ? (
        <div className="px-3 py-6 text-center text-xs text-[var(--destructive)]">
          Failed to load API keys.
        </div>
      ) : keys.length === 0 && !showForm && !newlyCreatedKey ? (
        <div className="px-3 py-6 text-center text-xs text-[var(--muted-foreground)]">
          No API keys yet. Generate one to get started.
        </div>
      ) : keys.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[11px] uppercase tracking-wider text-[var(--muted-foreground)]">
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Key</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium">Last Used</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <KeyRow key={k.id} apiKey={k} fundSlug={fundSlug} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {/* New key banner */}
      {newlyCreatedKey && (
        <NewKeyBanner fullKey={newlyCreatedKey} onDismiss={() => setNewlyCreatedKey(null)} />
      )}

      {/* Generate form */}
      {showForm && (
        <GenerateKeyForm
          onGenerate={(name) =>
            createMutation.mutate({ name, scopes: ["read", "write"] })
          }
          onCancel={() => setShowForm(false)}
          isPending={createMutation.isPending}
        />
      )}
    </SectionPanel>
  );
}
