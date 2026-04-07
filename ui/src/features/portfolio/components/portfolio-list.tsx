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
      <div className="mb-4 flex items-center justify-between">
        <span />
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white"
        >
          + Create Portfolio
        </button>
      </div>

      {!portfolios || portfolios.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">No portfolios found.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {portfolios.map((p) => (
            <Link
              key={p.id}
              href={`/${fundSlug}/portfolio/${p.id}`}
              className="rounded-lg border border-[var(--border)] p-4 transition-colors hover:bg-[var(--muted)]"
            >
              <h3 className="font-medium">{p.name}</h3>
              <p className="text-sm text-[var(--muted-foreground)]">{p.strategy ?? "No strategy"}</p>
            </Link>
          ))}
        </div>
      )}

      {showCreate && <CreatePortfolioDialog onClose={() => setShowCreate(false)} />}
    </div>
  );
}
