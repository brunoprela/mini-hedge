"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { portfoliosQueryOptions } from "../api";
import { CreatePortfolioDialog } from "./create-portfolio-dialog";

export function PortfolioList() {
  const { fundSlug } = useFundContext();
  const { data: portfolios, isLoading } = useQuery(portfoliosQueryOptions(fundSlug));
  const [showCreate, setShowCreate] = useState(false);

  if (isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Loading portfolios...</p>;
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-end">
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded-md bg-[var(--primary)] px-3 py-1 text-xs font-medium text-white"
        >
          + Create Portfolio
        </button>
      </div>

      {!portfolios || portfolios.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">No portfolios found.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--table-border)] bg-[var(--table-header)] text-left text-xs text-[var(--muted-foreground)]">
                <th className="px-3 py-1.5 font-medium">Name</th>
                <th className="px-3 py-1.5 font-medium">Strategy</th>
                <th className="px-3 py-1.5 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {portfolios.map((p) => (
                <tr key={p.id} className="border-b border-[var(--table-border)] last:border-b-0 hover:bg-[var(--table-row-hover)]">
                  <td className="px-3 py-1.5 font-medium">{p.name}</td>
                  <td className="px-3 py-1.5 font-mono text-xs text-[var(--muted-foreground)]">{p.strategy ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right">
                    <Link
                      href={`/${fundSlug}/portfolio/${p.id}`}
                      className="text-xs font-medium text-[var(--primary)] hover:underline"
                    >
                      Open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <CreatePortfolioDialog onClose={() => setShowCreate(false)} />}
    </div>
  );
}
